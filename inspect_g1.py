from pathlib import Path

import mujoco

path = (
    str(Path(__file__).resolve().parent / "unitree_ros/robots/g1_description/g1_29dof.xml")
)

model = mujoco.MjModel.from_xml_path(path)

print("=== UNITREE G1 ===")
print("Joints:", model.njnt)
print("Actuators:", model.nu)

print("\n=== JOINTS ===")
for i in range(model.njnt):
    name = mujoco.mj_id2name(
        model, mujoco.mjtObj.mjOBJ_JOINT, i
    )
    print(i, name)

print("\n=== ACTUATORS ===")
for i in range(model.nu):
    name = mujoco.mj_id2name(
        model, mujoco.mjtObj.mjOBJ_ACTUATOR, i
    )
    print(i, name)
