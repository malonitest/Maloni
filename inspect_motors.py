
from pathlib import Path

import mujoco

path = (
    str(Path(__file__).resolve().parent / "unitree_ros/robots/g1_description/g1_29dof.xml")
)

model = mujoco.MjModel.from_xml_path(path)

print("=== UNITREE G1 MOTOR CONFIGURATION ===")
print("Total actuators:", model.nu)

for i in range(model.nu):
    name = mujoco.mj_id2name(
        model,
        mujoco.mjtObj.mjOBJ_ACTUATOR,
        i
    )

    print(
        f"{i}: {name} | "
        f"ctrlrange={model.actuator_ctrlrange[i]} | "
        f"gain={model.actuator_gainprm[i][0]} | "
        f"bias={model.actuator_biasprm[i][1]}"
    )
print("\n=== RIGHT ARM CONTROL DETAILS ===")

for i in range(22, 29):
    name = mujoco.mj_id2name(
        model, mujoco.mjtObj.mjOBJ_ACTUATOR, i
    )

    joint_id = model.actuator_trnid[i, 0]

    joint_name = mujoco.mj_id2name(
        model, mujoco.mjtObj.mjOBJ_JOINT, joint_id
    )

    print(
        f"{i}: {name}\n"
        f"  Joint: {joint_name}\n"
        f"  Transmission: {model.actuator_trntype[i]}\n"
        f"  Dynamics: {model.actuator_dyntype[i]}\n"
        f"  Gain type: {model.actuator_gaintype[i]}\n"
        f"  Bias type: {model.actuator_biastype[i]}\n"
        f"  Control limited: {model.actuator_ctrllimited[i]}\n"
        f"  Force limited: {model.actuator_forcelimited[i]}\n"
        f"  Force range: {model.actuator_forcerange[i]}\n"
        f"  Joint limits: {model.jnt_range[joint_id]}\n"
    )