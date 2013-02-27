#!/usr/bin/env python

# Hack to prevent stupid "TypeError: 'NoneType' object is not callable" error
# in multiprocessing/util.py _exit_function when running `python
# setup.py test` (see
# http://www.eby-sarna.com/pipermail/peak/2010-May/003357.html)
for m in ('multiprocessing', 'billiard'):
    try:
        __import__(m)
    except ImportError:
        pass

from setuptools import setup, find_packages

dev_requires = [
    'flake8>=1.6',
]

tests_require = [
    'blinker>=1.1',
    'celery>=2.5',
    'Django>=1.2',
    'django-celery>=2.5',
    'exam>=0.5.2',
    'Flask>=0.8',
    'logbook',
    'mock',
    'nose',
    'pep8',
    'pytz',
    'pytest',
    'pytest-django',
    'tornado',
    'unittest2',
    'webob',
]


setup(
    name='mr.poe',
    version='3.1.16-3',
    author='David Cramer',
    author_email='dcramer@gmail.com',
    url='http://github.com/collective/mr.poe',
    description='mr.poe is a fork of raven-python for ancient versions of Python',
    long_description=open('README.rst', 'rb').read(),
    packages=find_packages(exclude=("tests",)),
    zip_safe=False,
    extras_require={
        'tests': tests_require,
        'dev': dev_requires,
    },
    test_suite='runtests.runtests',
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'raven = raven.scripts.runner:main',
        ],
        'paste.filter_app_factory': [
            'raven = raven.contrib.paste:sentry_filter_factory',
        ],
    },
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Operating System :: OS Independent',
        'Topic :: Software Development',
        'Programming Language :: Python :: 2.4',
        'Framework :: Zope2',
    ],
)
