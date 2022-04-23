// 30 low, 31 low - 1048590
// 30 high, 31 low - 9437198
// 30 low, 31 high - 5242894
// 30 high, 31 high - 13631502
#include <Entropy.h>

#define ledPin 13
#define controllerTrigger 30 // pin to trigger controller
#define beagleTrigger 31 // pin to beagle trigger in

#define bothPins GPIO8_DR
#define bothLow 1048590
#define bothHigh 13631502

void setup() {
	Serial.begin(115200);

  Entropy.Initialize();

  pinMode(ledPin, OUTPUT);
  pinMode(controllerTrigger, OUTPUT);
  pinMode(beagleTrigger, OUTPUT);

  digitalWriteFast(ledPin, LOW);
  digitalWriteFast(controllerTrigger, LOW);
  digitalWriteFast(beagleTrigger, LOW);
 
}

void loop() {

  // set both pins low
  bothPins = bothLow;
  digitalWriteFast(ledPin, LOW);
  // random delay with floor at twice the highest measured latency from mister sheet
  delay(Entropy.random(400,1000));

  //set both pins high
  bothPins = bothHigh;
  digitalWriteFast(ledPin, HIGH);
  // random delay with floor at twice the highest measured latency from mister sheet
  delay(Entropy.random(400,1000));
}
