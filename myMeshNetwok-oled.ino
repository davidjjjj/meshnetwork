#include <brzo_i2c.h>

//************************************************************
// A simple ESP8266 painlessMesh application:
// - send MeshTopology to serial port. Received by the Python app on PC side to visualize the mesh topology
// - receive 'broadcast' or 'single' command from serial port, which is sent by the Python app on PC side 
// - read and write 2 parameters, i.e. 'timer' and 'brightness'
// 
// Yoppy ~ Dec 2018
//
//************************************************************
#include <painlessMesh.h>   // looks like need to install painlessMesh first.
#include <ESP8266WiFi.h>
#include <ESP8266WiFiMesh.h>
//#include <Wire.h>  // Only needed for Arduino 1.6.5 and earlier
//#include <brzo_i2c.h> // Only needed for Arduino 1.6.5 and earlier
#include "SSD1306Brzo.h"

SSD1306Brzo display(0x3c, D3, D5);

// some gpio pin that is connected to an LED...
// on my rig, this is 5, change to the right number of your LED.
#define   LED             2       // GPIO number of connected LED, ON ESP-12 IS GPIO2

#define   BLINK_PERIOD    3000 // milliseconds until cycle repeat
#define   BLINK_DURATION  100  // milliseconds LED is on for

#define   MESH_SSID       "whateverYouLike"
#define   MESH_PASSWORD   "somethingSneaky"
#define   MESH_PORT       5555

// Prototypes
//void sendMessage(); 
void receivedCallback(uint32_t from, String & msg);
void newConnectionCallback(uint32_t nodeId);
void changedConnectionCallback(); 
void nodeTimeAdjustedCallback(int32_t offset); 
void delayReceivedCallback(uint32_t from, int32_t delay);


Scheduler     userScheduler; // to control your personal task
painlessMesh  mesh;

// parameters to be set and queried by PC 
// instead of primitive data-type,  it is implemented as JSON object for easier and flexible usage 
StaticJsonBuffer<100> jsonBuffer;
JsonObject& params = jsonBuffer.createObject();

// uint32_t num_of_message_sent = 0;
//uint32_t prev_num_of_message_sent = 0;
bool calc_delay = true; 
SimpleList<uint32_t> nodes;
 char strBuffer[30];
int request_i=0;

String oledstr1;
String oledstr2;
String oledstr3;
String oledstr4;
String oledstr5;

void sendMessage() ; // Prototype
Task taskSendMessage( TASK_SECOND * 2  /*10000UL*/, TASK_FOREVER, &sendMessage ); // start with a one or x second(s) interval

// void printStatus();
// Task taskPrintStatus( TASK_SECOND * 1  /*10000UL*/, TASK_FOREVER, &printStatus ); // start with a one second interval
//float dimLevel[2];

void readSerial();
// serial speed 115.200 bps = 115.000/10bit/1000ms = 11.5 chars/ms.
// read serial every 20 ms. at most 20*11.5 = 230 chars accumulated in serial buffer each task run
Task taskReadSerial(TASK_MILLISECOND * 20, TASK_FOREVER, &readSerial);
// Task to blink the number of nodes
Task blinkNoNodes;
bool onFlag = false;
void oledFlashDisplay();

//........................setup...........................
void setup() {
  Serial.begin(115200);
  pinMode(LED, OUTPUT);

  //mesh.setDebugMsgTypes( ERROR | MESH_STATUS | CONNECTION | SYNC | COMMUNICATION | GENERAL | MSG_TYPES | REMOTE ); // all types on
  //mesh.setDebugMsgTypes(ERROR | DEBUG | CONNECTION | COMMUNICATION);  // set before init() so that you can see startup messages
  //mesh.setDebugMsgTypes(S_TIME /*| DEBUG | CONNECTION*/);  // set before init() so that you can see startup messages

  display.init();
  display.flipScreenVertically();
  display.setFont(ArialMT_Plain_10);
  oledstr5= "setting up mesh....";
  oledFlashDisplay();

  mesh.init(MESH_SSID, MESH_PASSWORD, &userScheduler, MESH_PORT);
  mesh.onReceive(&receivedCallback);
  mesh.onNewConnection(&newConnectionCallback);
  mesh.onChangedConnections(&changedConnectionCallback);
  mesh.onNodeTimeAdjusted(&nodeTimeAdjustedCallback);
  mesh.onNodeDelayReceived(&delayReceivedCallback);

  userScheduler.addTask( taskSendMessage );
  taskSendMessage.enable();

//   userScheduler.addTask( taskPrintStatus );
//   taskPrintStatus.enable();

  userScheduler.addTask(taskReadSerial);
  taskReadSerial.enable();

  blinkNoNodes.set(BLINK_PERIOD, (mesh.getNodeList().size() + 1)* 2, []() {
     // If on, switch off, else switch on
      if (onFlag)
        onFlag = false;
      else
        onFlag = true;
      blinkNoNodes.delay(BLINK_DURATION);

      if (blinkNoNodes.isLastIteration()) {
        // Finished blinking. Reset task for next run 
        // blink number of nodes (including this node) times
        blinkNoNodes.setIterations((mesh.getNodeList().size() + 1) * 2);
        // Calculate delay based on current mesh time and BLINK_PERIOD
        // This results in blinks between nodes being synced
        blinkNoNodes.enableDelayed(BLINK_PERIOD - 
            (mesh.getNodeTime() % (BLINK_PERIOD*1000))/1000);
      }
  });   //以上設定每週期閃動次數為節點數二倍
  userScheduler.addTask(blinkNoNodes);
  blinkNoNodes.enable();

  randomSeed(analogRead(A0));
  oledstr5= "looping....";
  oledFlashDisplay();
}


void oledFlashDisplay() {
  display.clear();
  display.drawString(0, 10,oledstr1);
  display.drawString(0, 20,oledstr2);
  display.drawString(0, 30,oledstr3);
  display.drawString(0, 40,oledstr4);
  display.drawString(0, 50,oledstr5);
  display.display();
}


void loop() {
  userScheduler.execute(); // it will run mesh scheduler as well
  mesh.update();
  digitalWrite(LED, !onFlag);  //閃完後保持常關
}

void sendMessage() {
     String msg = "My node ID:  ";
     msg += mesh.getNodeId();

     oledstr4=msg;
     
     // msg += " myFreeMemory: " + String(ESP.getFreeHeap());
     // Serial.printf("%s\n", msg.c_str());     
     //mesh.sendBroadcast(msg);
     //num_of_message_sent += 1;
     
    int nodeOrder=1;
  
     String meshTopology = mesh.subConnectionJson();
     if (meshTopology != NULL)
          Serial.printf("MeshTopology: %s\n", meshTopology.c_str());

  sprintf(strBuffer, "loop #%d..Node%d.", request_i++, ESP.getChipId());
  oledstr2=(String)strBuffer;
  oledFlashDisplay();
  
     nodes = mesh.getNodeList();
     // Serial.printf("Num nodes: %d\n", nodes.size());
  
     if (calc_delay) {
          SimpleList<uint32_t>::iterator node = nodes.begin();
 
          //   display.clear();
          
          while (node != nodes.end()) {
               mesh.startDelayMeas(*node);        // send a delay measurement request

 
    
     sprintf(strBuffer, " %u", *node);
     oledstr3=(String)strBuffer;
     oledFlashDisplay();

       nodeOrder++;
       node++;
          }

          
       calc_delay = false;                     // Comment out to do delay measurement repeatedly
     }

     //Serial.printf("Sending message: %s\n", msg.c_str());  
     //taskSendMessage.setInterval( random(TASK_SECOND * 1, TASK_SECOND * 5));  // between 1 and 5 seconds

      StaticJsonBuffer<80> jsonBuffer;
      JsonObject& sensormsg = jsonBuffer.createObject();
      
}

void readSerial()
{
	  String data;
	  // whenever the first char is found, we continously waiting for subsequent chars until no more.
	  // exit waiting if 1000 ms of idle
	  if (Serial.available())
	  {
		  data = Serial.readStringUntil('\n');
		  Serial.println("Serial received:" + data);

		  DynamicJsonBuffer jsonBuffer(150);
		  JsonObject &dataJSON = jsonBuffer.parseObject(data);

          //if the data is of a JSON string, --> forward it to other nodes
          if (dataJSON.success())
          {
               Serial.println("[ESP] Serial prints: A valid JSON string");

               // because ArduinoJSON is based on 'null object pattern', check the key by reading the object
               // if the key is not available, return 0
               // "dest-id" is coupled to JSON string sent from PC. So should match exactly
               uint32_t id = dataJSON["dest-id"];

               // brodcast
               if (id == 1)
               {
                    Serial.println("[ESP] WiFi sending broadcast message");
                    mesh.sendBroadcast(data);				

                    return;
               }
               // single
               else if (id > 1)
               {
                    Serial.println("[ESP] WiFi sending single message");
                    mesh.sendSingle(id, data);
               }
               // no "id" key
               else if (id == 0)
               {
                    Serial.println("[ESP] id is not available.");
               }
          }
          // if it is a plain string     
          else if (data.equals("myFreeMemory-query"))
               Serial.printf( "myFreeMemory-reply: %d\n", ESP.getFreeHeap() );

	  }
}


void receivedCallback(uint32_t from, String &msg) 
{
  //Serial.printf("startHere: Received from %u msg=%s\n", from, msg.c_str()
  //Serial.printf("startHere: Received from %u msg=%s\n", from, msg.c_str());
	String meshTopology = mesh.subConnectionJson();
	if (meshTopology != NULL)
		Serial.printf("MeshTopology: %s\n", meshTopology.c_str());

	Serial.printf("[ESP] WiFi received: %s\n", msg.c_str());

	// added by yoppy
	DynamicJsonBuffer jsonBuffer(100);
	JsonObject &message = jsonBuffer.parseObject(msg);

	if (message.success())
	{
	
		if(message.containsKey("query")) {
			JsonArray& queryParam = message["query"];			
			Serial.print("[ESP] Number of query params:");
			Serial.println (queryParam.size());			
			
			StaticJsonBuffer<80> jsonBuffer;
			JsonObject& msg = jsonBuffer.createObject();
			
			//TODO: instead of all paramters, probably want to reply selective parameters
               String param_3 = "freeMem";
               params[param_3] = ESP.getFreeHeap();
			msg["query-reply"] = params;
			msg["src-id"] = mesh.getNodeId();
			String str;
			msg.printTo(str);
			Serial.println(str);			
			
			uint32_t dest = from;
			mesh.sendSingle( dest, str);

		}
		else if(message.containsKey("set")) {
			Serial.println("[ESP] <found a 'set' key.>");
						
			JsonObject& setParams = message["set"];

			String param_1 = "timer";
			String param_2 = "brightness";
			uint32_t dest = from;

			if( setParams.containsKey(param_1) & setParams.containsKey(param_2) ) {
				uint32_t timer = setParams[param_1];
				//Serial.printf( "TIMER going to be set: %d\n", timer );	
				params[param_1] = timer;

				uint32_t brightness = setParams[param_2];
                    //Serial.printf("Debug: de-JSON 'brightness': %d", brightness);
				//Serial.printf( "BRIGHTNESS going to be set: %d\n", brightness );
				params[param_2] = brightness;

				//Serial.println("Params after being set:");
				//params.printTo(Serial);
				String setReply = "{ \"set-reply\": \"success!\" }";
				mesh.sendSingle(dest, setReply);
			}
			else {
				String setReply = "{ \"set-reply\": \"failed!\" }";
				mesh.sendSingle(dest, setReply );				
			}
		}
		else if(message.containsKey("query-reply")){
			Serial.println("[ESP] <found a 'query-reply' key.>");
		}
		else if(message.containsKey("set-reply")){
			Serial.println("[ESP] <found a 'set-reply' key.>");
		}

		else Serial.println("[ESP] Keys not found.");
  }					
	  
}

void newConnectionCallback(uint32_t nodeId) {
  // Reset blink task
  onFlag = false;
  
  blinkNoNodes.setIterations((mesh.getNodeList().size() + 1) * 2);
  blinkNoNodes.enableDelayed(BLINK_PERIOD - (mesh.getNodeTime() % (BLINK_PERIOD*1000))/1000);
  
  sprintf(strBuffer,"New node,Id = %u\n", nodeId);
 // display.clear();
  display.drawString(0, 20, strBuffer);
  display.display();
  Serial.printf(strBuffer);

  calc_delay = true;
}

void changedConnectionCallback() {
  char nodechars[10];
  int nodeOrder=1;
  Serial.printf("Changed connections %s\n", mesh.subConnectionJson().c_str());
  // Reset blink task
  onFlag = false;
  blinkNoNodes.setIterations((mesh.getNodeList().size() + 1) * 2);
  blinkNoNodes.enableDelayed(BLINK_PERIOD - (mesh.getNodeTime() % (BLINK_PERIOD*1000))/1000);
 
  nodes = mesh.getNodeList();

  Serial.printf("Num nodes: %d\n", nodes.size());
  Serial.printf("Connection list:");

  //display.clear();
  display.drawString(0, 20, "Connection list:");
  display.display();


  SimpleList<uint32_t>::iterator node = nodes.begin();
  while (node != nodes.end()) {
    Serial.printf(" %u", *node);
 //   display.clear();
     display.drawString(0, 10, "node:");
      sprintf(nodechars, " %u", *node);
     display.drawString(0,10+10*nodeOrder, nodechars);
       display.display();
    node++;
    nodeOrder++;
  }
  Serial.println();
  calc_delay = true;
}

void nodeTimeAdjustedCallback(int32_t offset) {
  Serial.printf("Adjusted time %u. Offset = %d\n", mesh.getNodeTime(), offset);
}

void delayReceivedCallback(uint32_t from, int32_t delay) {
  Serial.printf("Delay to node %u is %d us\n", from, delay);
}


/* void printStatus () {
     String msg ;     
     msg += "My free memory: " + String(ESP.getFreeHeap()) + ". Messages sent:" + String(num_of_message_sent) + " .Messages sent/s:" + String(num_of_message_sent-prev_num_of_message_sent);
     Serial.printf("%s\n", msg.c_str());
     prev_num_of_message_sent = num_of_message_sent;
} */
