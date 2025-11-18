import math

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan


class TwistLidarStop(Node):
    """
    Node that:
    - Publishes a constant Twist (vx, vy, w)
    - Reads LaserScan
    - Stops the robot when the distance in the motion direction
      is below a given threshold.
    """

    def __init__(self):
        super().__init__('twist_lidar_stop_node')

        # ---- Parameters ----
        # Linear velocities in robot frame (m/s)
        self.declare_parameter('vx', 0.3)
        self.declare_parameter('vy', 0.0)

        # Angular velocity (rad/s)
        self.declare_parameter('w', 0.0)

        # Stop distance (m)
        self.declare_parameter('stop_distance', 0.3)

        # Angular window around motion direction (deg)
        # e.g. 10° → consider rays within ±10° of motion direction
        self.declare_parameter('angle_window_deg', 10.0)

        self.vx = float(self.get_parameter('vx').value)
        self.vy = float(self.get_parameter('vy').value)
        self.w = float(self.get_parameter('w').value)
        self.stop_distance = float(self.get_parameter('stop_distance').value)
        self.angle_window_deg = float(self.get_parameter('angle_window_deg').value)

        # Publisher /cmd_vel
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # Subscriber /scan
        self.lidar_sub = self.create_subscription(
            LaserScan,
            '/scan',
            self.lidar_callback,
            10
        )

        # Internal state
        self.obstacle_distance = float('inf')
        self.motion_blocked = False

        # Timer to publish Twist periodically
        self.timer = self.create_timer(0.1, self.timer_callback)

        self.get_logger().info(
            f"TwistLidarStop started with vx={self.vx:.2f} m/s, "
            f"vy={self.vy:.2f} m/s, w={self.w:.2f} rad/s, "
            f"stop_distance={self.stop_distance:.2f} m, "
            f"angle_window={self.angle_window_deg:.1f} deg"
        )

    def lidar_callback(self, scan: LaserScan):
        """Process LaserScan and compute distance in direction of motion."""
        # If no linear motion, we cannot define a motion direction
        lin_speed = math.hypot(self.vx, self.vy)
        if lin_speed < 1e-3:
            # Only rotation or stopped: do not block by distance
            self.obstacle_distance = float('inf')
            self.motion_blocked = False
            return

        # Motion direction in robot frame (deg), 0° = front, +90° = left, -90° = right
        motion_angle_deg = math.degrees(math.atan2(self.vy, self.vx))

        angle_min_deg = math.degrees(scan.angle_min)
        angle_increment_deg = math.degrees(scan.angle_increment)

        min_dist_in_dir = float('inf')

        for i, distance in enumerate(scan.ranges):
            # Raw lidar angle (depends on how the sensor publishes)
            angle_lidar_deg = angle_min_deg + i * angle_increment_deg

            # Lidar is mounted with 180° shift, adapt to robot frame
            angle_robot_deg = angle_lidar_deg + 180.0
            if angle_robot_deg > 180.0:
                angle_robot_deg -= 360.0

            # Filter invalid distances
            if not math.isfinite(distance) or distance <= 0.0:
                continue
            if distance < scan.range_min or distance > scan.range_max:
                continue

            # Keep only rays within the angular window around motion direction
            if abs(angle_robot_deg - motion_angle_deg) <= self.angle_window_deg:
                if distance < min_dist_in_dir:
                    min_dist_in_dir = distance

        self.obstacle_distance = min_dist_in_dir

        # Update blocked state
        if min_dist_in_dir < self.stop_distance:
            if not self.motion_blocked:
                self.get_logger().warn(
                    f"Obstacle detected at {min_dist_in_dir:.2f} m in motion direction "
                    f"({motion_angle_deg:.1f}°). Stopping robot."
                )
            self.motion_blocked = True
        else:
            # If no ray in the window, min_dist_in_dir will be inf → not blocked
            if self.motion_blocked and math.isfinite(self.obstacle_distance):
                self.get_logger().info("Path cleared, resuming motion.")
            self.motion_blocked = False

    def timer_callback(self):
        """Periodically publish /cmd_vel depending on obstacle distance."""
        twist = Twist()

        if self.motion_blocked:
            # Publish zero Twist to stop
            self.cmd_pub.publish(twist)
            return

        # No obstacle: publish commanded twist
        twist.linear.x = self.vx
        twist.linear.y = self.vy
        twist.angular.z = self.w

        self.cmd_pub.publish(twist)


def main(args=None):
    rclpy.init(args=args)
    node = TwistLidarStop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Stop robot before shutting down
        stop_twist = Twist()
        node.cmd_pub.publish(stop_twist)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
