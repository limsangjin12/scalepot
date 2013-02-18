from setuptools import setup


with open('requirements.txt', 'r') as req:
    require_packages = [p.strip() for p in req]


setup(
    name='scalepot',
    version='0.1',
    url='http://github.com/limsangjin12/scalepot',
    author='Sangjin Lim',
    author_email='limsangjin12@gmail.com',
    install_requires=require_packages,
    entry_points={
        'console_scripts': [
            'scalepot = scalepot.main:main',
        ]
    }
)
