
# -*- coding: utf-8 -*-
# Created by: PyQt5 UI code generator 5.5.1

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

import dialog
import serial_util as su
from node_mapping import recursive_node_mapping
import json

# For embedding matplotlib(used for plotting NetworkX graph) navigation toolbar on our app window
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

import networkx as nx
print(nx.__path__)

global oldJsonString

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("ESP8266 Mesh Network Visualizer")
        self.mainX = 600
        self.mainY = 600
        self.valmap = {'Me': 'gold'}   #此處定義結點顏色相關之字典，由{結點ID:顏色}組成
        self.size = {'size': '200'}      #此处定义节点颜色相关的字典，又{节点：颜色}组成
        self.rssi = {'Me': 'Signal'}
        self.node_labels={'Me': 'gold'}
        MainWindow.resize(self.mainX, self.mainY)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.figure, self.node_collection = self.setupPlot  # yoppy

        # this is the Canvas Widget that displays the `figure`
        # it takes the `figure` instance as a parameter to __init__
        # 这是显示图形的画布小部件
        # 它将figure实例作为参数__
        self.canvas = FigureCanvas(self.figure)
        self.canvas.draw()

        # register button pressed event
        self.cid = self.canvas.mpl_connect('button_press_event', self.onclick)

        # this is the Navigation widget
        # it takes the Canvas widget and a parent
        self.toolbar = NavigationToolbar(self.canvas, self)

        # init and open serial port
        # SET COMxx to the corresponding serial port number used by the ESP
        self.comPortNum = 'COM4'   ####################################
        self.ser_ref = su.init_serial(comPort=self.comPortNum)

        # References of dialog boxes appearing upon clicking nodes
        # 单击节点时出现的对话框的引用
        self.singleDial = None
        self.bcDial = None

        # create a thread to read from serial:
        # - for checking mesh topology changes. whenever there is a change, the mesh is redrawn
        # - for receiving replies from other nodes
        # 用于检查网格拓扑更改。只要有变化，网格就会重新绘制
        # -用于接收来自其他节点的回复
        ser_read_thread = SerialThread(self.ser_ref)
        ser_read_thread.updateNodeSig.connect(self.redrawMesh)
        ser_read_thread.queryReplySig.connect(self.forwardQueryReply)
        ser_read_thread.myFreeMemSig.connect(self.forwardMyFreeMem)
        ser_read_thread.sensorValueSig.connect(self.forwardSensorValue)
       # ser_read_thread.sensorValueSig.connect(self.forwardRssiValue)
     #   ser_read_thread.sensorValueSig.connect(self.lineEdit)
        ser_read_thread.start()

        # For testing purpose, define a lineEdit. It accepts only 2-digit numeric
        # It was used to test redrawing number of circles according to the number given in the lineEdit
        # Not used anymore
        # 为了进行测试，请定义一个lineEdit。它只接受2位数字
        # 它用于根据lineEdit中给定的数字测试重绘圆的数目
        # 不再使用
        self.lineEdit = QLineEdit(self.centralwidget)
        self.lineEdit.setMaxLength(2)
        self.lineEdit.setAlignment(Qt.AlignLeft)
        self.lineEdit.setValidator(QIntValidator())
        #self.lineEdit.setText("11")
        # Setting a connection between slider position change and on_changed_value function
        # self.lineEdit.returnPressed.connect(self.redrawMesh)
        # 设置滑块位置更改和on_changed_value函数之间的连接
        # self.lineEdit.returnPressed.connect（self.redrawMesh）

        # define label for showing serial port settings
        # 定义显示串行端口设置的标签
        self.serialSettingLabel = QLabel(self.centralwidget)
        serialSetting = 'Port: ' + str(self.ser_ref.port) + '. Baud rate: ' + str(self.ser_ref.baudrate)
        self.serialSettingLabel.setText(serialSetting)

        # Create a test button
        # Used for sending commands to serial port
        self.testButton = QPushButton()
        self.testButton.setText('Test Button')
        self.testButton.clicked.connect(self.write_serial)

        # self.menubar = QtWidgets.QMenuBar(MainWindow)
        # self.menubar.setGeometry(QtCore.QRect(0, 0, 571, 25))
        # self.menubar.setObjectName("menubar")
        # MainWindow.setMenuBar(self.menubar)
        # self.statusbar = QtWidgets.QStatusBar(MainWindow)
        # self.statusbar.setObjectName("statusbar")
        # MainWindow.setStatusBar(self.statusbar)

        MainWindow.setCentralWidget(self.centralwidget)

        layout = QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        layout.addWidget(self.lineEdit)
        layout.addWidget(self.testButton)
        layout.addWidget(self.serialSettingLabel)
        self.centralwidget.setLayout(layout)
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    @property
    def setupPlot(self):
        # create networkx graph
        self.G = nx.Graph()
        self.G.add_node(1)

        # add nodes
        # for node in nodes:
        #     self.G.add_node(node)

        # add edges
        # for edge in graph:
        #     self.G.add_edge(edge[0], edge[1])
        #self.pos = nx.shell_layout(self.G)
        # draw() is in nx_pylab.py
        # By default draw() returns nothing. draw() is modified to return cf & node_collection
        # Because we need cf (plot figure reference) here to embed it on our top app window
        # node_collection is used when we need to detect whether a node is clicked
        cf, node_collection = nx.draw(self.G)

        return cf, node_collection


    # on clicking UI
    # We want to detect when a node on the plot is clicked. Just a simple interactive session.
    # If node 'Me' is clicked, open Broadcast dialog box which send/read to all other nodes
    # Other than node 'Me', meaning we want to interact with that particular node
    # 单击用户界面时
    # 我们要检测何时单击绘图上的节点。只是一个简单的互动环节。
    # 如果单击节点“Me”，则打开“广播”对话框，向所有其他节点发送/读取
    # 而不是节点“Me”，这意味着我们希望与该特定节点交互
    def onclick(self,event):
        cont, ind = self.node_collection.contains(event)
               # when a node is clicked
        if cont:
            nodes = nx.nodes(self.G)
            nodelist = list (nodes)
            nodeId = nodelist[ ind['ind'][0] ]

        if nodeId=='Me':
            self.bcDial = dialog.BroadcastDialog()
            self.bcDial.popUp(self.ser_ref,nodeId)
        else:
            self.singleDial = dialog.SingleDialog()
            self.singleDial.popUp(self.ser_ref, nodeId)


    # Not sure if this is the best way
    # To forward signal from class SerialThread to class SingleDialog
    # 不确定这是最好的方法
    # 将信号从类SerialThread转发到类SingleDialog
    def forwardQueryReply(self, queryReply):
        self.singleDial.query_reply(queryReply)

    # To forward signal from class SerialThread to class BroadcastDialog
    def forwardMyFreeMem(self, freeMemMsg):
        self.bcDial.displayMyFreeMem(freeMemMsg)
    #依感測值字串，改變結點顏字典值
    def forwardSensorValue(self, sensorValueMsg):
        global oldJsonString
        #print("forwardSensorValue")
        #在字典顏色被改變後，需要重畫結點圖
        #我們的方法是改變oldJsonString，使它與現有的結點不同
        #從而啟動redrawMesh
        sensorJson = json.loads(sensorValueMsg)
        nodeID = sensorJson["node-id"]
        sensorValue = sensorJson["sensor-value"]
        Temp = sensorJson["Temp"]
        Hum = sensorJson["Hum"]
        nodesize = int(float(sensorValue)*20)
        if (float(sensorValue) > 30):
            nodeColor = "red"
            #nodesize = 600
           # self.G.nodes.Weight = "1000"
        elif (float(sensorValue) > 25):
            nodeColor = "yellow"
            #nodesize = 500
        elif (float(sensorValue) >= 20):
            nodeColor = "green"
            #nodesize = 1000
            #print(Temp+Hum)
        elif (float(sensorValue) < 20):
            nodeColor = "blue"
            #nodesize = 300
        if (self.valmap.get(nodeID)!=nodeColor):
            #print(self.valmap.get(nodeID))
            self.valmap[nodeID] = nodeColor
            oldJsonString = None
            #print("done")
        #self.bcDial.displaySensorValue(sensorValueMsg)
        if (self.size.get(nodeID)!=nodesize):
            #print(self.valmap.get(nodeID))
            self.size[nodeID] = nodesize
            oldJsonString = None

        RssiValue = sensorJson["rssi"]
        if (RssiValue >= -55):
            rssivalue = 4
            print(rssivalue)
        # name = 1;
    # return lineRssi
        elif (RssiValue >= -66 and RssiValue < -55):
            rssivalue = 3
            print(rssivalue)
        # return lineRssi
        elif (RssiValue >= -77 and RssiValue < -67):
            rssivalue = 2
        # return lineRssi
        elif (RssiValue >= -88 and RssiValue < -78):
            rssivalue = 1
        elif (RssiValue < -88):
            rssivalue = 0
        if (self.rssi.get(nodeID) != rssivalue):
            # print(self.valmap.get(nodeID))
            self.rssi[nodeID] = rssivalue
            oldJsonString = None
    """   
    def  forwardRssiValue(self,sensorValueMsg):
        global oldJsonString
        sensorJson1 = json.loads(sensorValueMsg)
        nodeID = sensorJson1["node-id"]
        RssiValue = sensorJson1["rssi"]
        if (RssiValue >= -55):
            rssivalue=4
            print(rssivalue)
            #name = 1;
           # return lineRssi
        elif (RssiValue >= -66 and RssiValue < -55):
            rssivalue=3
            print(rssivalue)
            #return lineRssi
        elif (RssiValue >= -77 and RssiValue < -67):
            rssivalue=2
            #return lineRssi
        elif (RssiValue >= -88 and RssiValue< -78):
            rssivalue =1
        elif (RssiValue < -88):
            rssivalue = 0
        if (self.name.get(nodeID)!=rssivalue):
            #print(self.valmap.get(nodeID))
            self.name[nodeID] = rssivalue
            oldJsonString = None
    """

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "ESP8266 Mesh 网络可视化"))
        #self.label.setText(_translate("MainWindow", "TextLabel"))
        #self.label_2.setText(_translate("MainWindow", "TextLabel"))

    # For testing purpose. Execute this function when the Test button is pressed.
    # 用于测试目的。按下测试按钮时执行此功能。
    def write_serial(self):
        self.ser_ref.write(b'{ "dest-id":2147321632, "query":["temp", "time", "date"] }\n')

    def redrawMesh(self, graph):
        self.figure.clear()
        self.G = graph
        #val_map = {'Me': 'gold'}

        # If node 'Me' exists, use 'gold'. Otherwise 'violet'
        values = [self.valmap.get(node, 'violet') for node in self.G.nodes()]
        size = [self.size.get(node, 500) for node in self.G.nodes()]
        namevalue=[self.rssi.get(node,'1') for node in self.G.nodes()]

        self.pos = nx.spring_layout(self.G)
        # This NetworkX draw() is modified to return cf and node_collection. By default, return nothing.
        cf, node_collection = nx.draw(self.G, self.pos, node_size=size, node_color=values, width=1, edge_color="lightblue",
                     font_weight='regular', font_family='Trebuchet MS', font_color='black')
        #在node_mapping.py中將邊的name定成它的一點nodeID
        edgeName = nx.get_edge_attributes(self.G,'name')
        #再這裡把它換成信號強度
        for key in edgeName.keys():
            edgeName[key]=self.rssi.get(edgeName[key],0)
        #print(edgeName)
        #nx.draw_networkx_edges(self.G,self.pos, edge_color="lightblue",label=True)
        self.canvas.figure = cf
        #nx.set_edge_attributes(self.G,name='name',values=namevalue)
        gnodes=self.G.nodes()
        #print(gnodes)
        #這裡試著把一些數據直接在圖上表式出來
        for node in gnodes:
            self.node_labels[node]=self.valmap.get(node, 'violet')+'\n'+str(node)
        nx.draw_networkx_labels(self.G, self.pos, labels=self.node_labels)
        #edge_labels = nx.get_edge_attributes(self.G,'name')
        #self.G.add_edge('Me',3166816842,name= namevalue)
        #信號強度用邊的label表示
        nx.draw_networkx_edge_labels(self.G, self.pos, font_size=10,alpha=0.5,rotate=True,edge_labels=edgeName)
        self.node_collection = node_collection  # used for checking whether mouse click event is in a node
        self.canvas.draw()

class SerialThread(QtCore.QThread):
    #updateNode = QtCore.pyqtSignal(int)
    updateNodeSig = QtCore.pyqtSignal(object)
    queryReplySig = QtCore.pyqtSignal(object)
    myFreeMemSig = QtCore.pyqtSignal(object)
    sensorValueSig = QtCore.pyqtSignal(object)

    def __init__(self, ser_ref):
        global oldJsonString
        QtCore.QThread.__init__(self)
        self.serialPort = ser_ref
        oldJsonString = None
        self.status = 5

    # def nodeMappingTest(self):
    #     size = 11
    #     nodeMapObj = NodeMapping(size, size)
    #     initNode = [int(size / 2), int(size/ 2)]                    # initial node position
    #     initDirection = [0, 1]                                      # initial direction vector
    #     nodeMap = BitArray2D(rows=size, columns=size)    # create 2D bit array of node map
    #     nodeMap[int(size / 2), int(size / 2)] = 1                   # initialize the starting node position at the window CENTER
    #     relationList = []                                           # list holding all relations
    #
    #     jsonString = json.loads(NodeMapping.meshTopo)
    #     nodeMapObj.recursive_node_mapping(jsonString, initNode, initDirection, nodeMap, relationList)
    #     return relationList, nodeMap
    # def getSerialSetting(self):
    #     return self.serialPort.getSerialSetting()
    def updateNetworkxGraph(self, meshString):

        graph = nx.Graph()
        try:
            jsonString = json.loads(meshString)
        except ValueError:
            print('Not a valid JSON Object')

        # If mesh string is empty, draw node 'Me' only
        if (jsonString.__len__() == 0):
            graph.add_node('Me')
        else:
            recursive_node_mapping(jsonString, 'Me', graph)
        #edgelist =graph.edges()
        #print("edgelist:")
        #print(edgelist)
        return graph


    def run(self):
        #下面二個新增變數都因考慮在繪圖完成前，不要太早呼叫redrawMesh而來
        getMesh = 0
        global oldJsonString
        while True:

            # Wait for new string from serial port
            while True:
                msgType, jsonString = su.read_json_string(self.serialPort)  # read a '\n' terminated line
                if jsonString != None:
                    break

            # Please uncomment to deliberately redraw mesh every time serial is received
            # Otherwise, the figure is only redrawn when there is a change in the mesh topology
            #self.oldJsonString = None

            if (msgType == 'MeshTopology'):
                # Check if the mesh topology has changed
                if oldJsonString != jsonString:
                #if jsonString != None:
                    graph = self.updateNetworkxGraph(jsonString)
                    oldJsonString = jsonString
                    self.updateNodeSig.emit(graph)
                    print(jsonString)
                    self.sleep(1)
                    #確認第一次繪圖已完成（結點已畫好），才啟動sensor傳值（改結點顏色）
                    getMesh = 1

            elif (msgType == 'query-reply'):
                self.queryReplySig.emit(jsonString)
                #self.sleep(1)

            elif (msgType == 'myFreeMem'):
                self.myFreeMemSig.emit(jsonString)
                #新增處理感測器字串程序
            elif (msgType == 'sensor-value' and getMesh==1 ):
                #print("get sensor value")
                self.sensorValueSig.emit(jsonString)

# class ChangeNodeThread(QtCore.QThread):
#     updateNode = QtCore.pyqtSignal(int)
#
#     def __init__(self):
#         QtCore.QThread.__init__(self)
#         self.i = 1
#
#     def run(self):
#         while True:
#             self.i += 1
#             self.updateNode.emit(self.i)
#             self.sleep(3)