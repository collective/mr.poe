#!/usr/bin/python
# -*- coding: utf-8 -*-

from inspect import getouterframes, currentframe, getinnerframes
import re
from raven.handlers.logging_handler import SentryHandler
from ZConfig.components.logger.factory import Factory
import logging
import sys
import traceback

from raven.utils.stacks import iter_stack_frames

logger = logging.getLogger(__name__)

SITE_ERROR_NO = re.compile("^((\d)+\.(\d)+\.(\d)+) ")
CRITICAL_LINE = re.compile("\n(.+?:.*?)\n")

class ZopeSentryHandlerFactory(Factory):

    def getLevel(self):
        return self.section.level

    def create(self):
        return ZopeSentryHandler(**self.section.__dict__)

    def __init__(self, section):
        Factory.__init__(self)
        self.section = section


class ZopeSentryHandler(SentryHandler):
    '''
    Zope unfortunately eats the stack trace information.
    To get the stack trace information and other useful information
    from the request object, this class looks into the different stack
    frames when the emit method is invoked.
    '''

    def __init__(self, *args, **kw):
        super(ZopeSentryHandler, self).__init__(*args, **kw)
        level = kw.get('level', logging.ERROR)
        self.setLevel(level)

    def emit(self, record):
        if record.levelno <= logging.ERROR:
            request = None
            exc_info = None
            for frame_info in getouterframes(currentframe()):
                frame = frame_info[0]
                if not request:
                    request = frame.f_locals.get('request', None)
                    if not request:
                        view = frame.f_locals.get('self', None)
                        request = getattr(view, 'request', None)
                if not exc_info:
                    exc_info = frame.f_locals.get('exc_info', None)
                    if not hasattr(exc_info, '__getitem__'):
                        exc_info = None
                if request and exc_info:
                    break

            if exc_info:
                record.exc_info = exc_info
                record.stack = \
                    iter_stack_frames(getinnerframes(exc_info[2]))
            if request:
                try:
                    body_pos = request.stdin.tell()
                    request.stdin.seek(0)
                    body = request.stdin.read()
                    request.stdin.seek(body_pos)
                    http = dict(headers=request.environ,
                                url=request.getURL(),
                                method=request.get('REQUEST_METHOD', ''),
                                host=request.environ.get('REMOTE_ADDR',
                                ''), data=body)
                    if 'HTTP_USER_AGENT' in http['headers']:
                        if 'User-Agent' not in http['headers']:
                            http['headers']['User-Agent'] = \
                                http['headers']['HTTP_USER_AGENT']
                    if 'QUERY_STRING' in http['headers']:
                        http['query_string'] = http['headers'
                                ]['QUERY_STRING']
                    setattr(record, 'sentry.interfaces.Http', http)
                    user = request.get('AUTHENTICATED_USER', None)
                    if user is not None:
                        user_dict = dict(id=user.getId(),
                                         is_authenticated=user.has_role('Authenticated'),
                                         email=user.getProperty('email') or '',
                                         roles=getattr(request, 'roles', ()))
                    else:
                        user_dict = {'is_authenticated': False, 'roles': getattr(request, 'roles', ())}
                    setattr(record, 'sentry.interfaces.User', user_dict)
                except (AttributeError, KeyError):
                    # We don't want to go recursive
                    pass
        
        error_number = SITE_ERROR_NO.findall(record.msg)
        if error_number:
            error_number = error_number[0][0]
        else:
            error_number = None
        
        if error_number:
            setattr(record, 'zope.errorid', error_number)
            error_type = [line for line in CRITICAL_LINE.findall(record.msg) if 'Traceback' not in line]
            if error_type:
                error_type = error_type[0]
                new_msg = record.msg.replace(error_number, error_type)
                record.message = record.msg = new_msg
        try:
            e=sys.exc_info()
            if e[0]:
                exception_info = {"type":e[0].__name__, 
                    "value":str(e[1]), "module":e[0].__module__}
                setattr(record, 'sentry.interfaces.Exception', exception_info)
                if error_number:
                    # This is covered by the rest of our metadata
                    new_msg = "%(type)s: %(value)s" % (exception_info)
                    record.msg = new_msg
                    record.message = new_msg
            if e[2]:
                tb_info = {"frames": []}
                frames = traceback.extract_tb(e[2])
                for frame in frames:
                    try:
                        # I am an evil thing
                        tb_module_guess = [m for m in sys.modules.keys() if m.replace(".","/") in frame[0]]
                        # Longest guessed module name
                        tb_module_guess = sorted(tb_module_guess, key=lambda x:len(x))[-1]
                    except:
                        tb_module_guess = None
                    tb_info["frames"].append(
                            {"filename":frame[0],
                             "lineno":frame[1],
                             "function":frame[2],
                             "context_line":frame[3],
                             "module":tb_module_guess,
                             })
                setattr(record, 'sentry.interfaces.Stacktrace', tb_info)
                lowest_frame = tb_info['frames'][-1]
                if "/" not in lowest_frame['filename']:
                    culprit = "%s %s" % (lowest_frame['filename'], lowest_frame['function'])
                    setattr(record, 'culprit', culprit)
        except (AttributeError, KeyError, TypeError):
            pass
        
        return super(ZopeSentryHandler, self).emit(record)
