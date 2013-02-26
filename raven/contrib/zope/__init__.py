#!/usr/bin/python
# -*- coding: utf-8 -*-

from inspect import getouterframes, currentframe, getinnerframes
import re
from raven.handlers.logging_handler import SentryHandler
from ZConfig.components.logger.factory import Factory
import logging

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
                #new_msg = record.msg.spiltlines()
                #old_first_line = new_msg[0]
                new_msg = record.msg.replace(error_number, error_type)
                #new_msg = "\n".join([new_first_line] + new_msg[1:])
                record.msg = new_msg
                #record.message = new_msg
        return super(ZopeSentryHandler, self).emit(record)
