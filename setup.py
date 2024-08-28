import os.path
from setuptools import setup, find_packages

pkg_name = 'qhonuskan-votes'
pkg_version = __import__(pkg_name.replace('-', '_')).__version__

# get requires from requirements/global.txt file.
requires_file_name = os.path.join(
    os.path.dirname(__file__), 'requirements', 'global.txt')
install_requires = [x.strip() for x in open(requires_file_name).readlines()]

setup(
    name=pkg_name,
    version=pkg_version,
    url='https://github.com/linkfloyd/qhonuskan-votes',
    license='GPL',
    description="Easy to use reddit like voting system for django models.",
    long_description=open('README.rst', 'r').read(),
    long_description_content_type="text/x-rst",
    author='Mirat Can Bayrak',
    author_email='miratcanbayrak@gmail.com',
    packages=find_packages(),
    install_requires=install_requires,
    zip_safe=False,
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Operating System :: OS Independent',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 3.2',
    ],
    python_requires='>=3.6',
)
