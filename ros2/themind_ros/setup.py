from setuptools import setup

package_name = "themind_ros"

setup(
    name=package_name,
    version="1.13.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/themind.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="RattusKing",
    description="theMind for ROS 2: a robot's senses in, a mind of its own beside it.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "bridge = themind_ros.bridge:main",
            "sim_robot = themind_ros.sim_robot:main",
        ],
    },
)
