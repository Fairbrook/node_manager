"""
Node Manager Action Server

Accepts ManageNode action goals to start or stop ROS2 nodes as subprocesses.
Each managed node is tracked by a user-supplied node_name label.
"""

import subprocess
import shutil
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from node_manager_interfaces.action import ManageNode


class NodeManagerServer(Node):
    def __init__(self):
        super().__init__('node_manager_server')
        self._processes: dict[str, subprocess.Popen] = {}

        self._action_server = ActionServer(
            self,
            ManageNode,
            'manage_node',
            execute_callback=self._execute,
            goal_callback=self._on_goal,
            cancel_callback=self._on_cancel,
        )
        self.get_logger().info('Node Manager Server ready on action "manage_node"')

    # ------------------------------------------------------------------
    # Goal / cancel callbacks (called from the action server thread)
    # ------------------------------------------------------------------

    def _on_goal(self, goal_request):
        label = goal_request.node_name
        if goal_request.start:
            if label in self._processes and self._processes[label].poll() is None:
                self.get_logger().warn(f'Rejecting start: "{label}" is already running')
                return GoalResponse.REJECT
            if not goal_request.package_name or not goal_request.executable_name:
                self.get_logger().warn('Rejecting start: package_name and executable_name are required')
                return GoalResponse.REJECT
        else:
            if label not in self._processes:
                self.get_logger().warn(f'Rejecting stop: "{label}" is not tracked')
                return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _on_cancel(self, goal_handle):
        self.get_logger().info('Cancel requested — accepted')
        return CancelResponse.ACCEPT

    # ------------------------------------------------------------------
    # Execute callback
    # ------------------------------------------------------------------

    def _execute(self, goal_handle):
        goal = goal_handle.request
        label = goal.node_name
        feedback = ManageNode.Feedback()
        result = ManageNode.Result()

        if goal.start:
            result = self._start_node(goal_handle, goal, label, feedback)
        else:
            result = self._stop_node(goal_handle, label, feedback)

        return result

    # ------------------------------------------------------------------
    # Start a node
    # ------------------------------------------------------------------

    def _start_node(self, goal_handle, goal, label, feedback):
        result = ManageNode.Result()

        ros2_bin = shutil.which('ros2')
        if ros2_bin is None:
            # Jazzy default install location
            ros2_bin = '/opt/ros/jazzy/bin/ros2'

        cmd = [ros2_bin, 'run', goal.package_name, goal.executable_name]
        if goal.ros_args:
            cmd += ['--ros-args'] + list(goal.ros_args)

        feedback.status = f'Launching: {" ".join(cmd)}'
        goal_handle.publish_feedback(feedback)
        self.get_logger().info(feedback.status)

        if goal_handle.is_cancel_requested:
            goal_handle.canceled()
            result.success = False
            result.message = 'Cancelled before launch'
            return result

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            goal_handle.abort()
            result.success = False
            result.message = f'Launch failed: {exc}'
            self.get_logger().error(result.message)
            return result

        self._processes[label] = proc
        feedback.status = f'Node "{label}" started (pid {proc.pid})'
        goal_handle.publish_feedback(feedback)
        self.get_logger().info(feedback.status)

        goal_handle.succeed()
        result.success = True
        result.message = f'Started "{label}" with pid {proc.pid}'
        return result

    # ------------------------------------------------------------------
    # Stop a node
    # ------------------------------------------------------------------

    def _stop_node(self, goal_handle, label, feedback):
        result = ManageNode.Result()
        proc = self._processes[label]

        if proc.poll() is not None:
            # Process already exited on its own
            del self._processes[label]
            goal_handle.succeed()
            result.success = True
            result.message = f'Node "{label}" had already exited (rc={proc.returncode})'
            return result

        feedback.status = f'Sending SIGTERM to "{label}" (pid {proc.pid})'
        goal_handle.publish_feedback(feedback)
        self.get_logger().info(feedback.status)

        proc.terminate()
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            feedback.status = f'SIGTERM timed out — sending SIGKILL to "{label}"'
            goal_handle.publish_feedback(feedback)
            self.get_logger().warn(feedback.status)
            proc.kill()
            proc.wait()

        del self._processes[label]
        goal_handle.succeed()
        result.success = True
        result.message = f'Stopped "{label}" (rc={proc.returncode})'
        self.get_logger().info(result.message)
        return result

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def destroy_node(self):
        for label, proc in list(self._processes.items()):
            if proc.poll() is None:
                self.get_logger().info(f'Shutting down — terminating "{label}"')
                proc.terminate()
                proc.wait(timeout=3.0)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = NodeManagerServer()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
