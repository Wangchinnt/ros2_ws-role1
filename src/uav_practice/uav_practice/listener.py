"""
Listener: subscribe to std_msgs/String on the `chatter` topic and log it.

Same pattern as uav_nav/gps_goto.py: subscription -> callback (there it reads /mavros/*
with best-effort QoS, qos_profile_sensor_data).
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from uav_practice.talker import make_qos


class Listener(Node):

    def __init__(self):
        super().__init__('listener')
        self.declare_parameter('reliability', 'reliable')  # 'reliable' | 'best_effort'
        reliability = self.get_parameter('reliability').value

        self.subscription = self.create_subscription(
            String, 'chatter', self.listener_callback, make_qos(reliability))
        self.get_logger().info('listener started: reliability=%s' % reliability)

    def listener_callback(self, msg):
        self.get_logger().info('I heard: "%s"' % msg.data)


def main(args=None):
    rclpy.init(args=args)
    node = Listener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
