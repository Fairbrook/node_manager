"""
Node Manager Action Client (CLI)

Usage examples
--------------
# Start a node:
  ros2 run node_manager node_manager_client -- start my_talker demo_nodes_py talker

# Stop a node:
  ros2 run node_manager node_manager_client -- stop my_talker

# Start with extra ROS args (e.g. remap a topic):
  ros2 run node_manager node_manager_client -- start my_talker demo_nodes_py talker \
      --ros-arg --remap chatter:=/my_chatter
"""

import sys
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node

from node_manager_interfaces.action import ManageNode


class NodeManagerClient(Node):
    def __init__(self):
        super().__init__('node_manager_client')
        self._client = ActionClient(self, ManageNode, 'manage_node')

    def send_goal(self, *, node_name: str, start: bool,
                  package_name: str = '', executable_name: str = '',
                  ros_args: list[str] | None = None) -> bool:
        if not self._client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('Action server not available')
            return False

        goal = ManageNode.Goal()
        goal.node_name = node_name
        goal.start = start
        goal.package_name = package_name
        goal.executable_name = executable_name
        goal.ros_args = ros_args or []

        self.get_logger().info(
            f'Sending goal: {"start" if start else "stop"} "{node_name}"'
        )

        send_future = self._client.send_goal_async(
            goal,
            feedback_callback=self._on_feedback,
        )
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()

        if not goal_handle.accepted:
            self.get_logger().error('Goal rejected by server')
            return False

        self.get_logger().info('Goal accepted — waiting for result …')
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result().result

        if result.success:
            self.get_logger().info(f'Success: {result.message}')
        else:
            self.get_logger().error(f'Failure: {result.message}')

        return result.success

    def _on_feedback(self, feedback_msg):
        self.get_logger().info(f'[feedback] {feedback_msg.feedback.status}')


def main(args=None):
    rclpy.init(args=args)

    argv = sys.argv[1:]
    # Strip leading '--' separator inserted by ros2 run
    if argv and argv[0] == '--':
        argv = argv[1:]

    def usage():
        print(__doc__)
        sys.exit(1)

    if len(argv) < 2:
        usage()

    command = argv[0]
    node_name = argv[1]

    if command == 'start':
        if len(argv) < 4:
            print('start requires: <node_name> <package_name> <executable_name> [ros_args...]')
            usage()
        package_name = argv[2]
        executable_name = argv[3]
        ros_args = argv[4:] if len(argv) > 4 else []
        start = True
    elif command == 'stop':
        package_name = ''
        executable_name = ''
        ros_args = []
        start = False
    else:
        print(f'Unknown command: {command!r}  (use "start" or "stop")')
        usage()

    client_node = NodeManagerClient()
    success = client_node.send_goal(
        node_name=node_name,
        start=start,
        package_name=package_name,
        executable_name=executable_name,
        ros_args=ros_args,
    )
    client_node.destroy_node()
    rclpy.shutdown()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
