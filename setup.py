from setuptools import find_packages, setup

package_name = 'node_manager'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='user',
    maintainer_email='user@example.com',
    description='Action server/client for starting and stopping ROS2 nodes at runtime',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'node_manager_server = node_manager.server:main',
            'node_manager_client = node_manager.client:main',
        ],
    },
)
