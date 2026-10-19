from pathlib import Path

import mujoco
import mujoco.viewer

model_path = (
    str(Path(__file__).resolve().parent / "unitree_ros/robots/g1_description/g1_29dof.xml")
)

print("Loading Unitree G1...")

model = mujoco.MjModel.from_xml_path(model_path)
data = mujoco.MjData(model)

print(f"Joints: {model.njnt}")
print(f"Actuators: {model.nu}")

mujoco.viewer.launch(model, data)
