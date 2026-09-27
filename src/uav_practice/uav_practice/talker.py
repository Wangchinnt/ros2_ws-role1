"""
Talker: periodically publish std_msgs/String on the `chatter` topic.

Same pattern as uav_nav/gps_goto.py: timer -> publish (there it is a 20 Hz setpoint
on /mavros/setpoint_position/local).
"""
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from std_msgs.msg import String


def make_qos(reliability):
    """Build a QoS profile by name: 'reliable' or 'best_effort'."""
    policy = ReliabilityPolicy.BEST_EFFORT if reliability == 'best_effort' \
        else ReliabilityPolicy.RELIABLE
    return QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10, reliability=policy)


class Talker(Node):

    def __init__(self):
        super().__init__('talker')
        # Foxy/Humble rule: declare_parameter ALWAYS gets a default value.
        self.declare_parameter('period', 0.5)            # seconds between messages
        self.declare_parameter('reliability', 'reliable')  # 'reliable' | 'best_effort'

        period = self.get_parameter('period').value
        reliability = self.get_parameter('reliability').value

        self.publisher_ = self.create_publisher(String, 'chatter', make_qos(reliability))
        self.timer = self.create_timer(period, self.timer_callback)
        self.count = 0
        self.get_logger().info(
            'talker started: period=%.2fs, reliability=%s' % (period, reliability))

    def timer_callback(self):
        msg = String()
        msg.data = 'Hello %d' % self.count
        self.publisher_.publish(msg)
        self.get_logger().info('Publishing: "%s"' % msg.data)
        self.count += 1


def main(args=None):
    rclpy.init(args=args)
    node = Talker()
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
