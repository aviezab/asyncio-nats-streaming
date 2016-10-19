from setuptools import setup
from nats_stream import __version__

setup(
    name='asyncio-nats-streaming-client',
    version=__version__,
    description='NATS Streaming client for Python Asyncio',
    long_description='Asyncio based Python client for NATS Streaming, a lightweight, high-performance cloud native '
                     'messaging system',
    classifiers=[
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5'
        ],
    url='https://github.com/mackeyja92/asyncio-nats-streaming',
    author='Jared Mackey',
    author_email='jared@mackey.tech',
    license='MIT License',
    install_requires=["asyncio-nats-client", "protobuf"],
    packages=['nats_stream', 'nats_stream.aio', 'nats_stream.pb'],
    zip_safe=True,
)