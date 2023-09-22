# Remote-Control-Forklift

Hi, the following is the documentation about my coolest project during a co-op at [The Raymond Corporation](raymondcorp.com).
The company is a part of Toyota Material Handling family and makes electric forklifts. I had the opportunity to work with them and put my python programming, hardware background to the test. 

For this project I developed a Python script which consisted an integration of a GUI(tkinter) and CAN library to send and receive CAN messages to and fro remote controller and a receiver (endpoint controller) on the truck using Bluetooth/ISM. The remote is capable of moving the truck in both direction, steering, lifting/dropping the forks, horn and many other truck specific functions. 

The code works on both windows and linux devices. We had a windows NUC and a raspberry pi attached to the truck and also powered by it. The code is designed to run on boot and hence there are no additional steps to get this system running when we key-on the truck.

The following links are the devices being used for this project. 
[Fort Robotics Remote](https://www.fortrobotics.com/wireless-industrial-remote-control)
[Fort Robotics Endpoint Controller](https://www.fortrobotics.com/endpoint-controller)

Some manuals from Fort Robotics site which might help.
[FORT Safe Remote Control Datasheet_0310.pdf](https://github.com/Yashsshah909/Remote-Control-Forklift/files/12702695/FORT.Safe.Remote.Control.Datasheet_0310.pdf)
[FORT Endpoint Controller Datasheet 0318.pdf](https://github.com/Yashsshah909/Remote-Control-Forklift/files/12702694/FORT.Endpoint.Controller.Datasheet.0318.pdf)
[FORT_Pro_SRCP_EPC_User_Manual-3-1-23.pdf](https://github.com/Yashsshah909/Remote-Control-Forklift/files/12702693/FORT_Pro_SRCP_EPC_User_Manual-3-1-23.pdf)
[FORT_Platform_Early_Access_Integration_Guide_400-0044_RevE (002).pdf](https://github.com/Yashsshah909/Remote-Control-Forklift/files/12702692/FORT_Platform_Early_Access_Integration_Guide_400-0044_RevE.002.pdf)
[FORT Safe Remote Control Pro Data Sheet 031822.pdf](https://github.com/Yashsshah909/Remote-Control-Forklift/files/12702691/FORT.Safe.Remote.Control.Pro.Data.Sheet.031822.pdf)

Image of the endpoint controller(yellow device) on the Truck.![IMG_8865](https://github.com/Yashsshah909/Remote-Control-Forklift/assets/78835534/c09403da-6875-4307-a271-0f4e4a09d9c3)

Mapping of remote buttons to their functions on the truck.![remote controller button function](https://github.com/Yashsshah909/Remote-Control-Forklift/assets/78835534/99d5a7e6-6c0a-4970-b726-db2d1d49f838)


A video of me operation the truck with the remote. 

https://github.com/Yashsshah909/Remote-Control-Forklift/assets/78835534/8a789eb0-e1a4-45d3-8ca2-d54b6499d0a5



