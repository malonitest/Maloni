
#include <algorithm>
#include <iostream>

class PDController
{
public:
    PDController(double kp, double kd, double max_torque)
        : kp_(kp), kd_(kd), max_torque_(max_torque)
    {
    }

    double calculate(
        double target,
        double position,
        double velocity)
    {
        double error = target - position;

        double torque =
            kp_ * error - kd_ * velocity;

        return std::clamp(
            torque,
            -max_torque_,
            max_torque_
        );
    }

private:
    double kp_;
    double kd_;
    double max_torque_;
};

int main()
{
    PDController shoulder(10.0, 1.0, 2.0);

    double target = 0.3;
    double position = 0.0;
    double velocity = 0.0;

    double torque = shoulder.calculate(
        target, position, velocity);

    std::cout << "MALONI G1 Controller\n";
    std::cout << "Torque: " << torque << " Nm\n";

    return 0;
}
