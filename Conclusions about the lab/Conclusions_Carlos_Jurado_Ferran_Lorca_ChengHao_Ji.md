# Laboratory session delivery


## Your first operating performances diagnostic

We first were familiarized with GitHub and Git commands to share a project while keeping backups. A fork of [GEB Projects Tools Repository](https://github.com/manelpuig/GEB_Projects_tools) was done and it was loaded locally using `git clone`. Then in `src\ESP32Test_Blink\src\main.cpp` was compiled and run on the device which made an led blink every second.

## The corrections you have made in the code

### - Change the 3D object orientation to "surgical_needle". What you have to change in the python code?

A part from selecting to show the "surgical_needle" in the `3D_Orientation.rdk` file and hiding the "plane", we modified the `Receive_data_RPY_IMU_world.py` file: we changed `object_NAME` in line 19 to "surgical_needle". 

![Surgical Needle](../Documentation/Images/lab-images-esp32-3d-projector/surgical-needle.png)

### - Is the orientation correct? why or why not?

The orientation of the plane was not correct, because when we rotated our xip around its "x" axis the plane rotated, instead, around the "y" plane. We were able to explain the misorientation as if the head of the plane was where the wings should be, which could be solved with a rotation of 90 degrees with respect to the z axis. 

### - Make the necessary corrections in the code and verify the correct orientation in roboDK virtual environment.

One way we found to solve this misorientation was to rotate the "z" axis by 90 degrees directly from the roboDK virtual environment, as the first image below shows. Once this was done, the plane was correctly oriented and rotating the xip around the "x" axis meant a rotation around the "x" of the virtual plane.

![Plane and change of axis](../Documentation/Images/lab-images-esp32-3d-projector/plane-change-axis.png)

![Receive data python script](../Documentation/Images/lab-images-esp32-3d-projector/receive-data-python-script.png)

The second image shows in intense colors (red, blue and green) the three axis of the initial wrong ortientation, whilst in pale colors the new corrected axis. The same methodology could probably be applied in the code when defining the axis, so it wouldn't need to be changed each time from the roboDK virtual environment.

## Your final conclusions

In this lab, we explored GitHub and Git programs, which facilitate sharing versions of a digital project across participants. We also got familiarized with the PlatformIO IDE extension, which enabled us to program the ESP32 device as a sensor of 3D orientation. We did find a bug that the device was not in download mode, which was solved by holding the restart button and connecting again to the computer. Throughout the sensor experiment, we used a local network provided by the supervisors so that the microcontroller could send data wirelessly into the `3D_Orientation.rdk`, which was in the computer.

