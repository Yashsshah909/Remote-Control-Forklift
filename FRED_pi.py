#!/usr/bin/env python
import can
import sys
import time
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import subprocess
import logging
import threading
import struct
import itertools
import os
os.system('sudo ip link set can0 up type can bitrate 125000')

appDate = "20230223"
appVersion = "0.10"
agv_node_id = 0x0b # changed from 0x0a to 0x0b
epc_node_id = 0x69
linux_loc = "/home/raymond-electrical-systems/"
win_loc = "H:\MCS\FRC_Rport"    # location for our windows computer - this is where the logger file gets created.

# Dictionary of write register messages to program configuration settings
FRC_CLEAR = {
    "SetLine1Segment0" :    {"id":(0x300+epc_node_id), "data":[0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00] },
}

FRC_RAYMOND = {
    "SetLine1Segment0" :    {"id":(0x300+epc_node_id), "data":[0x00, 0x00, 0x52, 0x41, 0x59, 0x4D, 0x4F, 0x4E] },
    "SetLine1Segment1" :    {"id":(0x300+epc_node_id), "data":[0x00, 0x01, 0x44, 0x20, 0x20, 0x20, 0x20, 0x20] },
}

# Filter for all relevant PDOs
filter_all = [
    {"can_id": (0x180+epc_node_id), "can_mask": 0x7FF, "extended": False},
    {"can_id": (0x280+epc_node_id), "can_mask": 0x7FF, "extended": False},
    {"can_id": (0x380+epc_node_id), "can_mask": 0x7FF, "extended": False},
    {"can_id": (0x480+epc_node_id), "can_mask": 0x7FF, "extended": False},
    {"can_id": (0x700+epc_node_id), "can_mask": 0x7FF, "extended": False},
]

# Filter for just reading heartbeat
filter_hb = [
    {"can_id": (0x480+epc_node_id), "can_mask": 0x7FF, "extended": False}
]

States = {
    "Init"    : 0,
    "Pre-Op"  : 1,
    "Op"      : 2,
    "Limit"   : 3,
    "Control" : 4,
    "Error"   : 99,
}

NMT_States = {
    "boot" : 0,
    "stop" : 4,
    "operation" : 5,
    "preop" : 127,
}

Numbers = {
    "1" : 0x01,
    "2" : 0x02,
    "3" : 0x04,
    "4" : 0x08,
}

Arrows = {
    "Down"  : 0x01,
    "Right" : 0x02,
    "Up"    : 0x04,
    "Left"  : 0x08,
}

Buttons = { 
    1 : Arrows,
    2 : Numbers,
}

ButtonLabels = ["X","Arrow","Button"]

rsvd_sec_key1 = 1
rsvd_sec_key2 = 1
rsvd_sec_key3 = 1
rsvd_sec_key4 = 1

GoCount = 0 # flag for NMT_GO function
desired_time = 3.0 # timer for NMT_GO function
start_time = time.time() # timer for NMT_GO function

class FRC():
    
    
    def __init__(self,master):
        if "linux" == sys.platform:
            self.defaultDirectory = linux_loc
        else:
            self.defaultDirecotyr = win_loc

        self.filter = filter_all
        self.updateInterval = 10
        self.msgCounters = {}
        self.msgCounters['Buttons'] = 0
        self.msgCounters['Sticks'] = 0
        self.msgCounters['Triggers'] = 0
        self.msgCounters['HB'] = 0
        self.msgCounters['FRC State'] = 0
        self.msgCounters['VM State'] = 0
        self.msgCounters['RxPDO'] = {}
        self.msgCounters['RxPDO']['1'] = 0
        self.msgCounters['RxPDO']['2'] = 0
        self.msgCounters['RxPDO']['3'] = 0
        self.msgCounters['RxPDO']['4'] = 0

        # Update rates in ms
        
        self.SDO1_update_rate = 10
        self.SDO2_update_rate = 10
        self.SDO3_update_rate = 10
        
        self.NMT_update_rate =20
        self.NMTPRE_update_rate =20
        
        self.TPDO1_update_rate = 20
        self.TPDO2_update_rate = 20
        self.TPDO3_update_rate = 20
        self.TPDO4_update_rate = 20
        
        self.state_machine_update_rate = 500
        
        # Truck Variables
        self.target_height = 10
        self.maxspd_tf = 1.5
        self.maxspd_ff = 0.3
        self.cnt_validation = 0x50
        self.toggle_bit_PDO2 = 0x00
        self.toggle_bit_PDO3 = 0x00
        
        # the following has been set to true as default instead as false like in original code.
        self.limit_traction = True
        self.limit_lift_lower = True
        self.limit_load_handler = True
        self.max_main_mast_lift_height = 6000
        self.max_mini_mast_lift_height = 1250

        self.traction_control = True
        self.steering_control = True
        self.lift_control = True
        self.aux_control = True
        
        # we dont care about this for now. 
        self.wire_guidance_control = False

        self.state = States["Init"]
        self.state_FRC = 0
        self.state_VM = 0

        # Stick/Trigger Variables
        self.lStick = 0
        self.rStick = 0
        self.lTrig = 0
        self.rTrig = 0

        self.triggerThresholdHigh = 60
        self.triggerThresholdLow = 40

        self.stickThresholdHigh = 60
        self.stickThresholdLow = 40

        self.internalTime = 0
        self.activeEPO = False

        self.active = {}

        self.active['Button'] = {}
        self.active['Button']['1'] = False
        self.active['Button']['2'] = False
        self.active['Button']['3'] = False
        self.active['Button']['4'] = False

        self.active['Arrow'] = {}
        self.active['Arrow']['Down'] = False
        self.active['Arrow']['Right'] = False
        self.active['Arrow']['Up'] = False
        self.active['Arrow']['Left'] = False

        self.active['Trigger'] = {}

        self.active['Trigger']['Left'] = {}
        self.active['Trigger']['Left']['Up'] = False
        self.active['Trigger']['Left']['Down'] = False

        self.active['Trigger']['Right'] = {}
        self.active['Trigger']['Right']['Up'] = False
        self.active['Trigger']['Right']['Down'] = False

        self.active['Stick'] = {}

        self.active['Stick']['Left'] = {}
        self.active['Stick']['Left']['Up'] = False
        self.active['Stick']['Left']['Down'] = False

        self.active['Stick']['Right'] = {}
        self.active['Stick']['Right']['Left'] = False
        self.active['Stick']['Right']['Right'] = False

        # Create all UI elements
        self.lblSpace = tk.Label(win,text=" ",font=("Tahoma",16),padx=30,pady=10)

        # Setup Buttons
        self.btnDefaultDisplay = tk.Button(win,text="Default\nDisplay",command=self.default_display_mode,font=("Tahoma",16),pady=10)
        self.btnUserTextDisplay = tk.Button(win,text="User Text\nDisplay",command=self.user_text_display_mode,font=("Tahoma",16),pady=10)
        #self.btnTriggerPDO3 = tk.Button(win,text="TPDO3",command=self.send_TPDO3,font=("Tahoma",16),pady=10)
        self.btnDebug = tk.Button(win,text="Debug",command=self.debug,font=("Tahoma",16),pady=10)
        self.btnQuit = tk.Button(win,text="Quit",command=self.win_quit,font=("Tahoma",16),pady=10)

        # Setup Auto/Manual Radio Buttons
        self.rdBtnAutoManual = tk.IntVar()
        self.rdBtnManual = tk.Radiobutton(win,text="Manual",variable=self.rdBtnAutoManual,value=0,font=("Tahoma",10))
        self.rdBtnAuto = tk.Radiobutton(win,text="Auto",variable=self.rdBtnAutoManual,value=1,font=("Tahoma",10))
        self.rdBtnAutoManual.set(1)

        ############################################################################################
        # Arrows v, >, ^. <
        ############################################################################################
        self.lblArrowText = tk.Label(win,text="Arrows",font=("Tahoma",16))
        self.strArrow = {}
        self.lbl = {}
        self.lbl["Arrow"] = {}

        self.strArrow["Down"] = tk.StringVar()
        self.lbl["Arrow"]["Down"] = tk.Label(win,textvariable=self.strArrow["Down"],font=("Tahoma",16),width=4)
        self.lbl["Arrow"]["Down"].config(bg='gray')
        self.strArrow["Down"].set("v")

        self.strArrow["Right"] = tk.StringVar()
        self.lbl["Arrow"]["Right"] = tk.Label(win,textvariable=self.strArrow["Right"],font=("Tahoma",16),width=4)
        self.lbl["Arrow"]["Right"].config(bg='gray')
        self.strArrow["Right"].set(">")

        self.strArrow["Up"] = tk.StringVar()
        self.lbl["Arrow"]["Up"] = tk.Label(win,textvariable=self.strArrow["Up"],font=("Tahoma",16),width=4)
        self.lbl["Arrow"]["Up"].config(bg='gray')
        self.strArrow["Up"].set("^")

        self.strArrow["Left"] = tk.StringVar()
        self.lbl["Arrow"]["Left"] = tk.Label(win,textvariable=self.strArrow["Left"],font=("Tahoma",16),width=4)
        self.lbl["Arrow"]["Left"].config(bg='gray')
        self.strArrow["Left"].set("<")
        ############################################################################################

        ############################################################################################
        # Buttons 1, 2, 3, 4
        ############################################################################################
        self.lblButtonText = tk.Label(win,text="Buttons",font=("Tahoma",16))
        self.strButton = {}
        self.lbl["Button"] = {}

        self.strButton["1"] = tk.StringVar()
        self.lbl["Button"]["1"] = tk.Label(win,textvariable=self.strButton["1"],font=("Tahoma",16),width=4)
        self.lbl["Button"]["1"].config(bg='gray')
        self.strButton["1"].set("1")

        self.strButton["2"] = tk.StringVar()
        self.lbl["Button"]["2"] = tk.Label(win,textvariable=self.strButton["2"],font=("Tahoma",16),width=4)
        self.lbl["Button"]["2"].config(bg='gray')
        self.strButton["2"].set("2")

        self.strButton["3"] = tk.StringVar()
        self.lbl["Button"]["3"] = tk.Label(win,textvariable=self.strButton["3"],font=("Tahoma",16),width=4)
        self.lbl["Button"]["3"].config(bg='gray')
        self.strButton["3"].set("3")

        self.strButton["4"] = tk.StringVar()
        self.lbl["Button"]["4"] = tk.Label(win,textvariable=self.strButton["4"],font=("Tahoma",16),width=4)
        self.lbl["Button"]["4"].config(bg='gray')
        self.strButton["4"].set("4")
        ############################################################################################

        ############################################################################################
        # Left Trigger
        ############################################################################################
        self.lblLeftTrig = tk.Label(win,text="Left Trig",font=("Tahoma",16))

        self.strLeftTrigDown = tk.StringVar()
        self.lblLeftTrigDown = tk.Label(win,textvariable=self.strLeftTrigDown,font=("Tahoma",16))
        self.lblLeftTrigDown.config(bg="gray")
        self.strLeftTrigDown.set("Down")

        self.strLeftTrigDownVal = tk.StringVar()
        self.lblLeftTrigDownVal = tk.Label(win,textvariable=self.strLeftTrigDownVal,font=("Tahoma",16),width=5)
        self.strLeftTrigDownVal.set("0%")

        self.strLeftTrigUp = tk.StringVar()
        self.lblLeftTrigUp = tk.Label(win,textvariable=self.strLeftTrigUp,font=("Tahoma",16))
        self.lblLeftTrigUp.config(bg="gray")
        self.strLeftTrigUp.set("Up")

        self.strLeftTrigUpVal = tk.StringVar()
        self.lblLeftTrigUpVal = tk.Label(win,textvariable=self.strLeftTrigUpVal,font=("Tahoma",16),width=5)
        self.strLeftTrigUpVal.set("0%")
        ############################################################################################

        ############################################################################################
        # Right Trigger
        ############################################################################################
        self.lblRightTrig = tk.Label(win,text="Right Trig",font=("Tahoma",16))

        self.strRightTrigDown = tk.StringVar()
        self.lblRightTrigDown = tk.Label(win,textvariable=self.strRightTrigDown,font=("Tahoma",16))
        self.lblRightTrigDown.config(bg="gray")
        self.strRightTrigDown.set("Down")

        self.strRightTrigDownVal = tk.StringVar()
        self.lblRightTrigDownVal = tk.Label(win,textvariable=self.strRightTrigDownVal,font=("Tahoma",16),width=5)
        self.strRightTrigDownVal.set("0%")

        self.strRightTrigUp = tk.StringVar()
        self.lblRightTrigUp = tk.Label(win,textvariable=self.strRightTrigUp,font=("Tahoma",16))
        self.lblRightTrigUp.config(bg="gray")
        self.strRightTrigUp.set("Up")

        self.strRightTrigUpVal = tk.StringVar()
        self.lblRightTrigUpVal = tk.Label(win,textvariable=self.strRightTrigUpVal,font=("Tahoma",16),width=5)
        self.strRightTrigUpVal.set("0%")
        ############################################################################################

        ############################################################################################
        # Left Stick
        ############################################################################################
        self.lblLeftStick = tk.Label(win,text="Left Stick",font=("Tahoma",16))

        self.strLeftStickDown = tk.StringVar()
        self.lblLeftStickDown = tk.Label(win,textvariable=self.strLeftStickDown,font=("Tahoma",16))
        self.lblLeftStickDown.config(bg="gray")
        self.strLeftStickDown.set("Down")

        self.strLeftStickDownVal = tk.StringVar()
        self.lblLeftStickDownVal = tk.Label(win,textvariable=self.strLeftStickDownVal,font=("Tahoma",16),width=5)
        self.strLeftStickDownVal.set("0%")

        self.strLeftStickUp = tk.StringVar()
        self.lblLeftStickUp = tk.Label(win,textvariable=self.strLeftStickUp,font=("Tahoma",16))
        self.lblLeftStickUp.config(bg="gray")
        self.strLeftStickUp.set("Up")

        self.strLeftStickUpVal = tk.StringVar()
        self.lblLeftStickUpVal = tk.Label(win,textvariable=self.strLeftStickUpVal,font=("Tahoma",16),width=5)
        self.strLeftStickUpVal.set("0%")
        ############################################################################################

        ############################################################################################
        # Right Stick
        ############################################################################################
        self.lblRightStick = tk.Label(win,text="Right Stick",font=("Tahoma",16))

        self.strRightStickLeft = tk.StringVar()
        self.lblRightStickLeft = tk.Label(win,textvariable=self.strRightStickLeft,font=("Tahoma",16))
        self.lblRightStickLeft.config(bg="gray")
        self.strRightStickLeft.set("Left")

        self.strRightStickLeftVal = tk.StringVar()
        self.lblRightStickLeftVal = tk.Label(win,textvariable=self.strRightStickLeftVal,font=("Tahoma",16),width=5)
        self.strRightStickLeftVal.set("0%")

        self.strRightStickRight = tk.StringVar()
        self.lblRightStickRight = tk.Label(win,textvariable=self.strRightStickRight,font=("Tahoma",16))
        self.lblRightStickRight.config(bg="gray")
        self.strRightStickRight.set("Right")

        self.strRightStickRightVal = tk.StringVar()
        self.lblRightStickRightVal = tk.Label(win,textvariable=self.strRightStickRightVal,font=("Tahoma",16),width=5)
        self.strRightStickRightVal.set("0%")
        ############################################################################################

        ############################################################################################
        # EPO
        ############################################################################################
        self.lblEPO = tk.Label(win,text="EPO",font=("Tahoma",20))
        self.lblEPO.config(bg="green")
        ############################################################################################

        ############################################################################################
        # State Machine
        ############################################################################################
        self.strState = tk.StringVar()
        self.lblState = tk.Label(win,textvariable=self.strState,font=("Tahoma",16))
        self.strState.set("Init")

        ############################################################################################
        # Setup grid of items
        # Column 0
        self.lbl["Arrow"]["Left"].grid(row=4,column=0,padx=10,pady=10)

        # Column 1
        self.lblLeftTrigDown.grid(row=0,column=1,padx=10,pady=10)
        self.lblLeftTrig.grid(row=1,column=1,padx=10,pady=10)
        self.lblLeftTrigUp.grid(row=2,column=1,padx=10,pady=10)
        self.lbl["Arrow"]["Up"].grid(row=3,column=1,padx=10,pady=10)
        self.lblArrowText.grid(row=4,column=1,padx=10,pady=10)
        self.lbl["Arrow"]["Down"].grid(row=5,column=1,padx=10,pady=10)
        self.lblLeftStickUp.grid(row=6,column=1,padx=10,pady=10)
        self.lblLeftStick.grid(row=7,column=1,padx=10,pady=10)
        self.lblLeftStickDown.grid(row=8,column=1,padx=10,pady=10)
        self.btnDefaultDisplay.grid(row=9,column=1,padx=10,pady=10)

        # Column 2
        self.lblLeftTrigDownVal.grid(row=0,column=2,padx=10,pady=10)
        self.lblLeftTrigUpVal.grid(row=2,column=2,padx=10,pady=10)
        self.lblLeftStickUpVal.grid(row=6,column=2,padx=10,pady=10)
        self.lblLeftStickDownVal.grid(row=8,column=2,padx=10,pady=10)
        self.lbl["Arrow"]["Right"].grid(row=4,column=2,padx=10,pady=10)

        # Column 3
        self.lblSpace.grid(row=0,column=3,padx=10,pady=10)
        self.lblState.grid(row=1,column=3,padx=10,pady=10)
        self.lblEPO.grid(row=3,column=3,padx=10,pady=10)
        self.rdBtnAuto.grid(row=5,column=3,padx=10,pady=10)
        self.rdBtnManual.grid(row=6,column=3,padx=10,pady=10)
        self.btnUserTextDisplay.grid(row=9,column=3,padx=10,pady=10)

        # Column 4
        self.lbl["Button"]["4"].grid(row=4,column=4,padx=10,pady=10)
        self.lblRightStickLeft.grid(row=7,column=4,padx=10,pady=10)
        self.lblRightStickLeftVal.grid(row=8,column=4,padx=10,pady=10)
        #self.btnTriggerPDO3.grid(row=9,column=4,padx=10,pady=10)

        # Column 5
        self.lblRightTrigDown.grid(row=0,column=5,padx=10,pady=10)
        self.lblRightTrig.grid(row=1,column=5,padx=10,pady=10)
        self.lblRightTrigUp.grid(row=2,column=5,padx=10,pady=10)
        self.lbl["Button"]["3"].grid(row=3,column=5,padx=10,pady=10)
        self.lblButtonText.grid(row=4,column=5,padx=10,pady=10)
        self.lbl["Button"]["1"].grid(row=5,column=5,padx=10,pady=10)
        self.lblRightStick.grid(row=7,column=5,padx=10,pady=10)
        self.btnDebug.grid(row=9,column=5,sticky="nsew",padx=10,pady=10)

        # Column 6
        self.lblRightTrigDownVal.grid(row=0,column=6,padx=10,pady=10)
        self.lblRightTrigUpVal.grid(row=2,column=6,padx=10,pady=10)
        self.lbl["Button"]["2"].grid(row=4,column=6,padx=10,pady=10)
        self.lblRightStickRight.grid(row=7,column=6,padx=10,pady=10)
        self.lblRightStickRightVal.grid(row=8,column=6,padx=10,pady=10)
        self.btnQuit.grid(row=9,column=6,sticky="nsew",padx=10,pady=10)
        ############################################################################################

        ############################################################################################
        # Open PCAN device - USB to CAN adapter
        ############################################################################################
        try:
            if "linux" == sys.platform:
                self.CANBus = can.interface.Bus(bustype="socketcan",channel='can0',bitrate=125000,can_filters=self.filter)
                logger.info("CAN Bus Active - can0")
            else:
                self.CANBus = can.interface.Bus(bustype="pcan",channel='PCAN_USBBUS1',bitrate=125000,can_filters=self.filter)
                logger.info("CAN Bus Active - pcan")
        except:
            logger.error("Initialization PCAN Driver Error")
            r = messagebox.showerror('PCAN USB-CAN Driver Error','Initialization Failed!\nCheck USB-CAN cable connections!')
            while(r is None):
                time.sleep(0.01)
            win.destroy()
            
        # opening listener for heatbeats
        self.lblSpace.after(self.updateInterval,self.CAN_Listener)
        
        #sending SDOs
        self.lblArrowText.after(self.SDO1_update_rate, self.send_SDO1)
        
        self.lblButtonText.after(self.SDO2_update_rate, self.send_SDO2)
        
        # sending GO_OP command to move the truck to opetational mode
        self.lblRightStickLeft.after(self.NMT_update_rate, self.send_NMT_GO)
        
        #sending TPDOs
        self.lblLeftTrigDown.after(self.TPDO1_update_rate, self.send_TPDO1)
        
        self.lblLeftTrigUp.after(self.TPDO2_update_rate, self.send_TPDO2)
        
        self.lblState.after(self.state_machine_update_rate, self.FRC_Process_State_Machine)

    def CAN_Listener(self):
        
        self.internalTime += self.updateInterval

        try:
            p = self.CANBus.recv(0.01)
            if p is not None:
                    
                if (0x180+epc_node_id) == p.arbitration_id:
                    self.msgCounters['Buttons'] += 1

                    #######################################################
                    # Buttons => Arrows / Numbers 
                    #######################################################
                    for i,b in Buttons.items(): # Index, Button (Button Dictionary containing Numbers/Arrows)
                        for k,v in b.items(): # Key, Value in Numbers/Arrows dictionaries
                            if p.data[i] & v:
                                #print(i,b,k,v)
                                if not(self.active[ButtonLabels[i]][k]):
                                    #print(f"{k} {ButtonLabels[i]}")
                                    self.active[ButtonLabels[i]][k] = True
                                    self.lbl[ButtonLabels[i]][k].config(bg='red')

                            elif not(p.data[i] & v):
                                if self.active[ButtonLabels[i]][k]:
                                    self.active[ButtonLabels[i]][k] = False
                                    self.lbl[ButtonLabels[i]][k].config(bg='gray')

                elif (0x280+epc_node_id) == p.arbitration_id:
                    self.msgCounters['Sticks'] += 1

                    d = p.data.hex()

                    #######################################################
                    # Left Stick
                    #######################################################
                    # Only care about Y Axis for Left Stick
                    lStick = int(d[6:8]+d[4:6],16)
                    self.lStick = lStick - 0x10000 if lStick & 0x8000 else lStick
                    if(lStick > 0x7FFF):
                        # Result is negative so Down Active
                        lStick ^= 0xFFFF 
                        lStick += 1
                        lStickDown = round((lStick/(32767))*100)
                        lStickUp = 0
                    else:
                        # Result is positive so Up Active
                        lStickUp = round((lStick/32767)*100)
                        lStickDown = 0

                    if lStickUp >= self.stickThresholdHigh:
                        if not(self.active['Stick']['Left']['Up']):
                            self.active['Stick']['Left']['Up'] = True
                            self.lblLeftStickUp.config(bg='red')
                    elif lStickUp <= self.stickThresholdLow:
                        if self.active['Stick']['Left']['Up']:
                            self.active['Stick']['Left']['Up'] = False
                            self.lblLeftStickUp.config(bg='gray')

                    if lStickDown >= self.stickThresholdHigh:
                        if not(self.active['Stick']['Left']['Down']):
                            self.active['Stick']['Left']['Down'] = True
                            self.lblLeftStickDown.config(bg='red')
                    elif lStickDown <= self.stickThresholdLow:
                        if self.active['Stick']['Left']['Down']:
                            self.active['Stick']['Left']['Down'] = False
                            self.lblLeftStickDown.config(bg='gray')
                    #######################################################

                    #######################################################
                    # Right Stick
                    #######################################################
                    # Only care about X Axis for Right Stick
                    rStick = int(d[10:12]+d[8:10],16)
                    self.rStick = rStick - 0x10000 if rStick & 0x8000 else rStick
                    if(rStick > 0x7FFF):
                        # Result is negative so Down Active
                        rStick ^= 0xFFFF 
                        rStick += 1
                        rStickLeft = round((rStick/(32767))*100)
                        rStickRight = 0
                    else:
                        # Result is positive so Up Active
                        rStickRight = round((rStick/32767)*100)
                        rStickLeft= 0

                    if rStickRight >= self.stickThresholdHigh:
                        if not(self.active['Stick']['Right']['Right']):
                            self.active['Stick']['Right']['Right'] = True
                            self.lblRightStickRight.config(bg='red')
                    elif rStickRight <= self.stickThresholdLow:
                        if self.active['Stick']['Right']['Right']:
                            self.active['Stick']['Right']['Right'] = False
                            self.lblRightStickRight.config(bg='gray')

                    if rStickLeft >= self.stickThresholdHigh:
                        if not(self.active['Stick']['Right']['Left']):
                            self.active['Stick']['Right']['Left'] = True
                            self.lblRightStickLeft.config(bg='red')
                    elif rStickLeft <= self.stickThresholdLow:
                        if self.active['Stick']['Right']['Left']:
                            self.active['Stick']['Right']['Left'] = False
                            self.lblRightStickLeft.config(bg='gray')
                    #######################################################

                    # Update all of the Stick Labels with 0-100% value
                    self.strLeftStickUpVal.set(str(lStickUp)+"%")
                    self.strLeftStickDownVal.set(str(lStickDown)+"%")
                    self.strRightStickRightVal.set(str(rStickRight)+"%")
                    self.strRightStickLeftVal.set(str(rStickLeft)+"%")

                elif (0x380+epc_node_id) == p.arbitration_id:
                    self.msgCounters['Triggers'] += 1

                    d = p.data.hex()
                    
                    #######################################################
                    # Left Trigger 
                    #######################################################
                    lTrig = int(d[2:4]+d[0:2],16)
                    self.lTrig = lTrig - 0x10000 if lTrig & 0x8000 else lTrig
                    if(lTrig > 0x7FFF):
                        # Result is negative so Down Active
                        lTrig ^= 0xFFFF 
                        lTrig += 1
                        lTrigDown = round((lTrig/(32767))*100)
                        lTrigUp = 0
                    else:
                        # Result is positive so Up Active
                        lTrigUp = round((lTrig/32767)*100)
                        lTrigDown = 0

                    #print(lTrig)
                    if lTrigUp >= self.triggerThresholdHigh:
                        if not(self.active['Trigger']['Left']['Up']):
                            self.active['Trigger']['Left']['Up'] = True
                            self.lblLeftTrigUp.config(bg='red')
                    elif lTrigUp <= self.triggerThresholdLow:
                        if self.active['Trigger']['Left']['Up']:
                            self.active['Trigger']['Left']['Up'] = False
                            self.lblLeftTrigUp.config(bg='gray')

                    if lTrigDown >= self.triggerThresholdHigh:
                        if not(self.active['Trigger']['Left']['Down']):
                            self.active['Trigger']['Left']['Down'] = True
                            self.lblLeftTrigDown.config(bg='red')
                    elif lTrigDown <= self.triggerThresholdLow:
                        if self.active['Trigger']['Left']['Down']:
                            self.active['Trigger']['Left']['Down'] = False
                            self.lblLeftTrigDown.config(bg='gray')
                    #######################################################

                    #######################################################
                    # Right Trigger 
                    #######################################################
                    rTrig = int(d[6:8]+d[4:6],16)
                    self.rTrig = rTrig - 0x10000 if rTrig & 0x8000 else rTrig
                    if(rTrig > 0x7FFF):
                        # Result is negative so Down Active
                        rTrig ^= 0xFFFF
                        rTrig += 1
                        rTrigDown = round((rTrig/(32767))*100)
                        rTrigUp = 0
                    else:
                        # Result is positive so Up Active
                        rTrigUp = round((rTrig/32767)*100)
                        rTrigDown = 0

                    #print(lTrig)
                    if rTrigUp >= self.triggerThresholdHigh:
                        if not(self.active['Trigger']['Right']['Up']):
                            #print('here')
                            self.active['Trigger']['Right']['Up'] = True
                            self.lblRightTrigUp.config(bg='red')
                    elif rTrigUp <= self.triggerThresholdLow:
                        if self.active['Trigger']['Right']['Up']:
                            self.active['Trigger']['Right']['Up'] = False
                            self.lblRightTrigUp.config(bg='gray')

                    if rTrigDown >= self.triggerThresholdHigh:
                        if not(self.active['Trigger']['Right']['Down']):
                            #print('here')
                            self.active['Trigger']['Right']['Down'] = True
                            self.lblRightTrigDown.config(bg='red')
                    elif rTrigDown <= self.triggerThresholdLow:
                        if self.active['Trigger']['Right']['Down']:
                            self.active['Trigger']['Right']['Down'] = False
                            self.lblRightTrigDown.config(bg='gray')
                    #######################################################

                    # Update all of the Trigger Labels with 0-100% value
                    self.strLeftTrigUpVal.set(str(lTrigUp)+"%")
                    self.strLeftTrigDownVal.set(str(lTrigDown)+"%")
                    self.strRightTrigUpVal.set(str(rTrigUp)+"%")
                    self.strRightTrigDownVal.set(str(rTrigDown)+"%")

                elif (0x480+epc_node_id) == p.arbitration_id:
                    self.msgCounters['HB'] += 1
                    print("data[4] = ", p.data[4])

                    #######################################################
                    # EPO 
                    #######################################################
                    if p.data[4] & 0x11:
                        self.internalTime = 0
                        if not(self.activeEPO):
                            self.activeEPO = True
                            self.lblEPO.config(bg="green")
                    elif not(p.data[4] & 0x11):
                        self.internalTime = 0
                        if self.activeEPO:
                            self.activeEPO = False
                            self.lblEPO.config(bg="red")

                elif (0x700+epc_node_id) == p.arbitration_id:
                    self.msgCounters['FRC State'] += 1
                    self.state_FRC = p.data[0]

                elif (0x700+agv_node_id) == p.arbitration_id:
                    self.msgCounters['VM State'] += 1
                    self.state_VM = p.data[0]
                
                elif (0x200+agv_node_id) == p.arbitration_id: 
                    # RxPDO1
                    self.msgCounters['RxPDO']['1'] += 1

                    if p.data[0] & 0x01:
                        self.limit_granted = True
                    else:
                        self.limit_granted = False
                     
                elif (0x300+agv_node_id) == p.arbitration_id: 
                    # RxPDO2
                    self.msgCounters['RxPDO']['2'] += 1

                    if p.data[0] & 0x01:
                        self.control_granted = True
                    else:
                        self.control_granted = False

                elif (0x400+agv_node_id) == p.arbitration_id: 
                    # RxPDO3
                    self.msgCounters['RxPDO']['3'] += 1
                elif (0x500+agv_node_id) == p.arbitration_id: 
                    # RxPDO4
                    self.msgCounters['RxPDO']['4'] += 1

        except:
            logger.error("CAN Receive Error")

        if self.internalTime > 2000:
            self.activeEPO = False
            self.lblEPO.config(bg="orange")

        #if self.msgCounters['Buttons'] < 10: # Useful Debug statement to just get a few packets right after startup
        self.lblSpace.after(self.updateInterval,self.CAN_Listener)
    
    def FRC_Process_State_Machine(self):
        
        #print(f"FRC State - {self.state} - {time.time()}")
        if States["Init"] == self.state: # "Init"
            #print(f"Init - {time.time()}")
            self.strState.set("Init")
            time.sleep(1)
            self.state = States["Pre-Op"]
            if States["Pre-Op"] != self.state:
                self.state = States["Pre-Op"]
                self.strState.set("Pre-Op")
                if NMT_States["preop"] == self.state_FRC and NMT_States["preop"] == self.state_VM:
                    self.state = States["Op"]
        
        elif States["Pre-Op"] == self.state: # "Pre-Op"
            #print(f"Pre-Operation - {time.time()}")
            self.strState.set("Pre-Op")

            if NMT_States["operation"] == self.state_FRC and NMT_States["operation"] == self.state_VM:
                self.state = States["Op"]

        elif States["Op"] == self.state: # Op
            self.strState.set("Op")

            if self.rdBtnAutoManual.get(): # Auto
                self.state = States["Limit"]

        elif States["Limit"] == self.state: # Limit
            self.strState.set("Limit")

            if not self.rdBtnAutoManual.get():
                self.state = States["Op"]
            elif self.rdBtnAutoManual.get() and self.limit_granted:
                self.state = States["Control"]

        elif States["Control"] == self.state: # Control
            self.strState.set("Control")

            if not self.rdBtnAutoManual.get():
                self.state = States["Op"]
            

        elif States["Error"] == self.state: # Error
            self.strState.set("Error")

        else: # Error
            print(f"Unknown State - {time.time()}")

        self.lblState.after(self.state_machine_update_rate,self.FRC_Process_State_Machine)

    # send_SDO1 to set up TPDO1
    def send_SDO1(self): 
        
        command_byte = 35 # 0x23h
        
        object_index = 5120 # 0x1400h
        
        sub_index = 1 #0x01h
        
        enable_data = 1073742336 + agv_node_id # 0x40000200h + agv_node_id
        
        framedata = struct.pack("<BHBI",command_byte,object_index,sub_index,enable_data)
        # BBBhhB describes the format of each Byte. B = unsigned char (int) (0 or positive values) (size = 1 byte), h = short (int) (size = 2 Bytes)
        
        self.CANBus.send(can.Message(arbitration_id=(0x600+agv_node_id),data=framedata,is_extended_id=False))
        # self.lblLeftTrigDown.after(self.SDO1_update_rate, self.send_SDO1)
    
    # send_SDO2 to set up TPDO2
    def send_SDO2(self):
        
        command_byte = 35 # 0x23h
        
        object_index = 5121 # 0x1401h
        
        sub_index = 1 #0x01h
        
        enable_data = 1073742592 + agv_node_id # 0x40000300h + agv_node_id
        
        framedata = struct.pack("<BHBI",command_byte,object_index,sub_index,enable_data)
        # BBBhhB describes the format of each Byte. B = unsigned char (int) (0 or positive values) (size = 1 byte), h = short (int) (size = 2 Bytes)
        
        self.CANBus.send(can.Message(arbitration_id=(0x600+agv_node_id),data=framedata,is_extended_id=False))
        # self.lblLeftTrigDown.after(self.SDO2_update_rate, self.send_SDO2)
        
    # send_SDO3 to set up TPDO3
    def send_SDO3(self):
        print("location 7")
        # time.sleep(0.5)
        
        command_byte = 35 # 0x23h
        
        object_index = 5122 # 0x1401h
        
        sub_index = 1 #0x01h
        
        enable_data = 1073742848 + agv_node_id # 0x40000300h + agv_node_id
        
        framedata = struct.pack("<BHBI",command_byte,object_index,sub_index,enable_data)
        # BBBhhB describes the format of each Byte. B = unsigned char (int) (0 or positive values) (size = 1 byte), h = short (int) (size = 2 Bytes)
        
        self.CANBus.send(can.Message(arbitration_id=(0x600+agv_node_id),data=framedata,is_extended_id=False))
        # self.lblLeftTrigDown.after(self.SDO3_update_rate, self.send_SDO3)
    
    def send_NMT_GO(self):
        global start_time
        global desired_time
        global GoCount
        
        first = 1 # 01h Operation mode
        second = 11 # 0b agv_node_id
        
        framedata = struct.pack("<BB",first,second)
        # BBBhhB describes the format of each Byte. B = unsigned char (int) (0 or positive values) (size = 1 byte), h = short (int) (size = 2 Bytes)
        
        if GoCount == 0:
            end_time = time.time()
            if (end_time - start_time) >= desired_time:
                self.CANBus.send(can.Message(arbitration_id=(0x000),data=framedata,is_extended_id=False)) #address 000 for the whole bus and 0b for the truck 
                GoCount += 1
                
        self.lblArrowText.after(self.NMT_update_rate, self.send_NMT_GO)
        
    def send_TPDO1(self):
        
        #print(f"TPDO1 - {time.time()}")
        
        # Byte 0 - Limit Flags
        # Bit 0 - Limit Request
        # if(self.rdBtnAutoManual.get()): # and (States["Limit"] == self.state or States["Control"] == self.state)):
        #     limit_request = 0
        #     # limit_request = 1 # Request limit
        # else:
            # limit_request = 0
        limit_request = 1
            
        # Bit 1 - Functionality depreciated
        # Bit 2 - Inhibit Traction
        
        # if self.limit_traction:
        #     limit_request |= 1 << 2
        # else:
        #     limit_request &= ~(1 << 2)

        # # Bit 3 - Inhibit Lift/Lower and Aux Lift/Lower
        # if self.limit_lift_lower:
        #     limit_request |= 1 << 3
        # else:
        #     limit_request &= ~(1 << 3)

        # # Bit 4 - Inhibit Load Handler/Aux
        # if self.limit_load_handler:
        #     limit_request |= 1 << 4
        # else:
        #     limit_request &= ~(1 << 4)

        # Bit 5 - AGV Controller E-Stop
        limit_request |= 1 << 5
        if self.activeEPO:
            limit_request |= 1 << 5 # &= ~(1 << 5)
        else:
            limit_request &= ~(1 << 5) # |= 1 << 5

        # Bit 6 - Horn
        if(self.active["Button"]["1"] and self.active["Button"]["4"] != True):
            limit_request |= 1
            limit_request |= 1 << 6
            # print("horn")
        else:
            limit_request &= ~(1 << 6)
        
        # Bit 7 - AGV Error FLag - error code needs to be written to SDO before setting this flag. upon this flag. drop control and limit.  
        # Not needed currently
        
        self.maxspd_tf = 20
        self.maxspd_ff = 20
        self.max_main_mast_lift_height = 6000
        self.max_mini_mast_lift_height = 1250
        
        if(self.active["Arrow"]["Up"] or self.active["Arrow"]["Down"]):
            self.maxspd_tf = 20
            self.maxspd_ff = 20
            limit_request |= 1
            
        if(self.active["Arrow"]["Up"]):
            self.maxspd_tf = 10 # default to 1.5 m/s (3.3 MPH)
            # print("setting max speed of tf as 10 (1 MPH)")
        
        # Byte 2 - FF Max Speed in 1/10 MPH (0-25.5 MPH)
        if(self.active["Arrow"]["Down"]):
            self.maxspd_ff = 10 # default to 0.3 m/s (0.6 MPH)
            # print("setting max speed of ff as 10 (1 MPH)")
            
        if(self.active["Arrow"]["Left"] or self.active["Arrow"]["Right"]):
            self.max_main_mast_lift_height = 6000
            self.max_mini_mast_lift_height = 1250
            limit_request |= 1
        
        # Bytes 3/4 - Max Main Mast Lift Height
        if(self.active["Arrow"]["Left"]):
            self.max_main_mast_lift_height = 150 #150
            # print("setting max lift height of main mast as 150")
        
        # Bytes 5/6 - Max Mini Mast Lift Height
        if(self.active["Arrow"]["Right"]):
            self.max_mini_mast_lift_height = 150 # 150
            # print("setting max lift height of mini mast as 150")
        
        # Byte 7 
        # Need to toggle rsvd_sec_key between 0 and 1 values.
        global rsvd_sec_key1 
        if (rsvd_sec_key1 == 0):
            rsvd_sec_key1 |= 1<<7
        else:
            rsvd_sec_key1 = 0
        
        framedata = struct.pack("<BBBhhB",limit_request,self.maxspd_tf,self.maxspd_ff,self.max_main_mast_lift_height,self.max_mini_mast_lift_height,rsvd_sec_key1)
        # BBBhhB describes the format of each Byte. B = unsigned char (int) (0 or positive values) (size = 1 byte), h = short (int) (size = 2 Bytes)
        
        self.CANBus.send(can.Message(arbitration_id=(0x200+agv_node_id),data=framedata,is_extended_id=False)) # changed from 0x180 to 0x200
        self.lblLeftTrigDown.after(self.TPDO1_update_rate, self.send_TPDO1)

    def send_TPDO2(self):
        
        #print(f"TPDO2 - {time.time()}")

        # Byte 0 - Control requests
        # Bit 0 - Control request (pre-req limit granted)
        if(self.rdBtnAutoManual.get()): # and (States["Control"] == self.state)): # 
            control_request = 1
        else:
            control_request = 0

        # Bit 1 - Traction control request (pre-req control granted)
        if(self.traction_control):
            control_request |= 1 << 1
        else :
            control_request &= ~(1 << 1)
            
        # to drop traction request
        if(self.active["Trigger"]["Left"]["Up"]):
            control_request &= ~(1 << 1)

        # Bit 2 - Steering control request (pre-req control granted)
        if(self.steering_control):
            control_request |= 1 << 2
        else :
            control_request &= ~(1 << 2)

        # Bit 3 - Lift control request (pre-req control granted)
        if(self.lift_control):
            control_request |= 1 << 3
        else :
            control_request &= ~(1 << 3)
            
        # to drop lift request
        if(self.active["Trigger"]["Left"]["Up"]):
            control_request &= ~(1 << 3)

        # Bit 4 - Aux control request (pre-req control granted)
        if(self.aux_control):
            control_request |= 1 << 4
        else :
            control_request &= ~(1 << 4)

        # Bit 5 - Wire Guidance Control Request (pre-req control granted)
        if(self.wire_guidance_control):
            control_request |= 1 << 5
        else :
            control_request &= ~(1 << 5)

        # Bit 6/7 - Not Used

        # Byte 1 - Traction throttle request % (-100 <-> +100, units 1% - Positive FF)
        # Byte 2/3 - Steering angle request (-180.00 <-> +180.00, units .01 deg - Positive CW viewed from above)
        throtval = self.lStick*(100.0/32767)
        steerval = self.rStick*(18000.0/32767)

        # if(self.active['Stick']['Left']["Up"] or self.active['Stick']['Left']["Down"]):
        #     print("throtle")
        
        # Full steering angle button
        if(self.active["Trigger"]["Left"]["Down"]):
            # Slow travle speed, full steer
            throtscale = 0.5
            steerscale = 1.0
        else:
            # Normal travel speed, limited steer
            throtscale = 1.0
            steerscale = 0.3
        
        throttle_request = -int(throtval*throtscale) # negative is forks firts and positive is traction first
        steer_request = int(steerval*steerscale)

        if(throttle_request > 100):
            throttle_request = 100
        elif(throttle_request < -100):
            throttle_request = -100

        if(steer_request > 17000):
            steer_request = 17000
        elif(steer_request < -17000):
            steer_request = -17000

        # Byte 4 - Main mast lift/lower request (-100 <-> +100, units 1% - Positive Lift)
        # Byte 5 - Mini mast lift/lower request (-100 <-> +100, units 1% - Positive Lift)
        liftval = int(self.rTrig*(100.0/32767))
        
        if(liftval > 100):
            liftval = 100
        elif(liftval < -100):
            liftval = -100

        main_lift_request = 0
        mini_lift_request = 0

        # If Left trigger is down, use right trigger as mini mast 
        if(self.active["Button"]["2"] == True and self.active["Button"]["4"]!=True):
            mini_lift_request = liftval
        elif(self.active["Button"]["4"]!=True):
            main_lift_request = liftval
            
        # Byte 6 - Not Used

        # Byte 7 - Reserved for Security Validation Key (0 = no security)
        # self.rsvd_sec_key = 0
        
        global rsvd_sec_key2 
        if (rsvd_sec_key2 == 0):
            rsvd_sec_key2 |= 1<<7
        else:
            rsvd_sec_key2 = 0

        framedata = struct.pack("<BbhbbB",control_request,throttle_request,steer_request,main_lift_request,mini_lift_request,rsvd_sec_key2)
        self.CANBus.send(can.Message(arbitration_id=(0x300+agv_node_id),data=framedata,is_extended_id=False)) # changed from 0x280 to 0x300
        
        self.lblLeftTrigUp.after(self.TPDO2_update_rate, self.send_TPDO2)

    def send_TPDO3(self):
        
        
        #print(f"TPDO3 - {time.time()}")

        # Byte 0 - Aux. request
        # Bit 0 - Auto Traverse and Rotate request (pre-req control and aux. control granted)
        aux_request = 0
        if(self.rdBtnAutoManual.get() and self.active["Button"]["1"] and self.active["Button"]["4"]): # and (States["Control"] == self.state) and self.aux_control):
            aux_request = 1
        else:
            aux_request = 0

        # Byte 1 - Turret rotate request (-100 <-> +100, units 1% - Positive CW viewed from above). Using right trigger for this.
        if(self.rdBtnAutoManual.get() and self.active["Button"]["4"]): # and (States["Control"] == self.state) and self.aux_control and self.active["Button"]["2"]):
            turret_rotate_request = int(self.rTrig*(100.0/32767))
            
            if(turret_rotate_request > 100):
                turret_rotate_request = 100
            elif(turret_rotate_request < -100):
                turret_rotate_request = -100
        else:
            turret_rotate_request = 0

        # Byte 2 - Mini mast traverse request (-100 <-> +100, units 1% - Positive right viewed from above). Using right stick for this.
        if(self.rdBtnAutoManual.get() and self.active["Button"]["4"] and self.active["Button"]["2"] != True): # and (States["Control"] == self.state) and self.aux_control and self.active["Button"]["2"]):
            mini_traverse_request = int(self.lTrig*(100.0/32767))
            
            if(mini_traverse_request > 100):
                mini_traverse_request = 100
            elif(mini_traverse_request < -100):
                mini_traverse_request = -100
        else:
            mini_traverse_request = 0

        # Byte 3 - Reach/Retract request (-100 <-> +100, units 1% - Positive reach viewed from above)
        if(self.rdBtnAutoManual.get() and self.active["Button"]["2"] and self.active["Button"]["3"] != True): # and (States["Control"] == self.state) and self.aux_control and self.active["Button"]["2"]):
            reach_request = int(self.lStick*(100.0/32767))
            
            if(reach_request > 100):
                reach_request = 100
            elif(reach_request < -100):
                reach_request = -100
        else:
            reach_request = 0
            
        # Byte 4 - Side-shift request (-100 <-> +100, units 1% - Positive right viewed from above)
        if(self.rdBtnAutoManual.get() and self.active["Button"]["2"]): # and (States["Control"] == self.state) and self.aux_control and self.active["Button"]["3"]):
            side_shift_request = int(self.rStick*(100.0/32767))
            
            if(side_shift_request > 100):
                side_shift_request = 100
            elif(side_shift_request < -100):
                side_shift_request = -100
        else:
            side_shift_request = 0

        # Byte 5 - Tilt request (-100 <-> +100, units 1% - Positive tilt up viewed from side)
        if(self.rdBtnAutoManual.get() and self.active["Button"]["2"] and self.active["Button"]["4"] != True): # and (States["Control"] == self.state) and self.aux_control and self.active["Button"]["3"]):
            tilt_request = int(self.lTrig*(100.0/32767))
            
            if(tilt_request > 100):
                tilt_request = 100
            elif(tilt_request < -100):
                tilt_request = -100
        else:    
            tilt_request = 0

        # Byte 6 - Fork positioner request (-100 <-> +100, units 1% - Positive indicates separation viewed from above)
        if(self.rdBtnAutoManual.get() and self.active["Button"]["3"] and self.active["Button"]["2"] != True): # and (States["Control"] == self.state) and self.aux_control and self.active["Button"]["3"]):
            fork_positioner_request = int(self.lStick*(100.0/32767))
            
            if(fork_positioner_request > 100):
                fork_positioner_request = 100
            elif(fork_positioner_request < -100):
                fork_positioner_request = -100
        else:
            fork_positioner_request = 0

        # Byte 7 - Reserved for Security Validation Key (0 = no security)
        # self.rsvd_sec_key = 0
        
        global rsvd_sec_key3 
        if (rsvd_sec_key3 == 0):
            rsvd_sec_key3 = 1
        else:
            rsvd_sec_key3 = 0

        framedata = struct.pack("<BbbbbbbB",aux_request,turret_rotate_request,mini_traverse_request,reach_request,side_shift_request,tilt_request,fork_positioner_request,0) # rsvd_sec_key3)
        self.CANBus.send(can.Message(arbitration_id=(0x400+agv_node_id),data=framedata,is_extended_id=False)) # changed from 0x380 to 0x400
        
        self.lblRightTrigDown.after(self.TPDO3_update_rate, self.send_TPDO3)

    def send_TPDO4(self):
        
        #print(f"TPDO4 - {time.time()}")
        global rsvd_sec_key4 
        if (rsvd_sec_key4 == 0):
            rsvd_sec_key4 = 1
        else:
            rsvd_sec_key4 = 0

        framedata = struct.pack("<BBBBBBBB",0,0,0,0,0,0,0,0) # rsvd_sec_key4)
        self.CANBus.send(can.Message(arbitration_id=(0x500+agv_node_id),data=framedata,is_extended_id=False)) # changed from 0x480 to 0x500
        
        self.lblRightTrigUp.after(self.TPDO3_update_rate, self.send_TPDO4)

    def default_display_mode(self):
        
        self.CANBus.send(can.Message(arbitration_id=(0x200+epc_node_id),data=[0x63,0x00,0x00,0x00,0x00,0x00,0x00,0x00],is_extended_id=False))

    def user_text_display_mode(self):
        
        self.CANBus.send(can.Message(arbitration_id=(0x200+epc_node_id),data=[0x63,0x01,0x00,0x00,0x00,0x00,0x00,0x00],is_extended_id=False))
        time.sleep(0.050)
        for m in FRC_RAYMOND.values():
            self.CANBus.send(can.Message(arbitration_id=m.get("id"), data=m.get("data"), is_extended_id=False))
            time.sleep(0.050)

    def debug(self):
        print("debug")
        print(f"\n\n------------------------------\n    Debug\n------------------------------")
        print(f"FRC Node ID: {epc_node_id}\t0x{epc_node_id:02x}")
        print(f"AGV Node ID: {agv_node_id}\t0x{agv_node_id:02x}")
        # print(f"VM Node ID: {vm_node_id}\t0x{vm_node_id:02x}")
        print(f"Button CAN-ID: {0x180+epc_node_id}\t0x{0x180+epc_node_id:02x}")
        print(f"Auto/Manual: {self.rdBtnAutoManual.get()}")
        print("\n------------------------------\n    Counters\n------------------------------")
        print(f"Buttons: {self.msgCounters['Buttons']}")
        print(f"Sticks: {self.msgCounters['Sticks']}")
        print(f"Triggers: {self.msgCounters['Triggers']}")
        print(f"HB: {self.msgCounters['HB']}")
        print(f"FRC State: {self.msgCounters['FRC State']}")
        print(f"VM State: {self.msgCounters['VM State']}")
        print(f"EPO Update Time: {self.internalTime}\n")

        for k,v in self.msgCounters['RxPDO'].items():
            print(f"RxPDO{k}: {v}")

        print()
        
        for i in self.active.items():
            print(i)

    def dummy(self):
        print("Debug")

    def win_quit(self):
        # Cleanup resources
        print("win_quit")
        logger.info("Quitting Application")
        win.quit()

if __name__ == '__main__':
    if sys.platform == "linux":
        logPath = linux_loc
    # elif sys.platform == "win32":
    else:
        logPath = win_loc
    # else:
    #     assert "WhereAmI?"

    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    handler = logging.FileHandler(logPath+"FRC.log")
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.info(f"FRC Test Starting Up - {appDate} {appVersion}")

    win = tk.Tk()
    win.title("FRC Remote Control Test")
    win.geometry("800x600")

    app = FRC(win)
    
    win.mainloop()
