import argparse
import asyncio
import binascii
from enum import Enum
import logging

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

from pynput.mouse import Button, Controller

mouse = Controller()

logger = logging.getLogger(__name__)

NUIMO_SERVICE_UUID = "f29b1525-cb19-40f3-be5c-7241ecb82fd2"
BUTTON_CHARACTERISTIC_UUID = "f29b1529-cb19-40f3-be5c-7241ecb82fd2"
TOUCH_CHARACTERISTIC_UUID = "f29b1527-cb19-40f3-be5c-7241ecb82fd2"
ROTATION_CHARACTERISTIC_UUID = "f29b1528-cb19-40f3-be5c-7241ecb82fd2"
FLY_CHARACTERISTIC_UUID = "f29b1526-cb19-40f3-be5c-7241ecb82fd2"
LED_MATRIX_CHARACTERISTIC_UUID = "f29b152d-cb19-40f3-be5c-7241ecb82fd2"
BATTERY_CHARACTERISTIC_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

LEGACY_LED_MATRIX_SERVICE = "f29b1523-cb19-40f3-be5c-7241ecb82fd1"
LEGACY_LED_MATRIX_CHARACTERISTIC_UUID = "f29b1524-cb19-40f3-be5c-7241ecb82fd1"

# TODO: Give services their actual names
UNNAMED1_SERVICE_UUID = "00001801-0000-1000-8000-00805f9b34fb"
UNNAMED2_SERVICE_UUID = "0000180a-0000-1000-8000-00805f9b34fb"
BATTERY_SERVICE_UUID = "0000180f-0000-1000-8000-00805f9b34fb"

SERVICE_UUIDS = [
    NUIMO_SERVICE_UUID,
    LEGACY_LED_MATRIX_SERVICE,
    UNNAMED1_SERVICE_UUID,
    UNNAMED2_SERVICE_UUID,
    BATTERY_SERVICE_UUID,
]


class Gesture(Enum):
    """
    A gesture that can be performed by the user on a Nuimo controller.
    """

    BUTTON_PRESS = 1
    BUTTON_RELEASE = 2
    SWIPE_LEFT = 3
    SWIPE_RIGHT = 4
    SWIPE_UP = 5
    SWIPE_DOWN = 6
    TOUCH_LEFT = (8,)
    TOUCH_RIGHT = (9,)
    TOUCH_TOP = (10,)
    TOUCH_BOTTOM = (11,)
    LONGTOUCH_LEFT = 12
    LONGTOUCH_RIGHT = 13
    LONGTOUCH_TOP = (14,)
    LONGTOUCH_BOTTOM = (15,)
    ROTATION = (16,)
    FLY_LEFT = (17,)
    FLY_RIGHT = (18,)
    FLY_UPDOWN = (19,)
    BATTERY_LEVEL = 20


async def button_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    gesture = Gesture.BUTTON_RELEASE if data[0] == 0 else Gesture.BUTTON_PRESS
    logger.info("BUTTON %s: %r", BUTTON_CHARACTERISTIC_UUID, gesture)
    if gesture == gesture.BUTTON_PRESS:
        mouse.press(Button.left)
        logger.info("Mouse pressed")
    elif gesture == gesture.BUTTON_RELEASE:
        mouse.release(Button.left)
        logger.info("Mouse released")


async def touch_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    gesture = {
        0: Gesture.SWIPE_LEFT,
        1: Gesture.SWIPE_RIGHT,
        2: Gesture.SWIPE_UP,
        3: Gesture.SWIPE_DOWN,
        4: Gesture.TOUCH_LEFT,
        5: Gesture.TOUCH_RIGHT,
        6: Gesture.TOUCH_TOP,
        7: Gesture.TOUCH_BOTTOM,
        8: Gesture.LONGTOUCH_LEFT,
        9: Gesture.LONGTOUCH_RIGHT,
        10: Gesture.LONGTOUCH_TOP,
        11: Gesture.LONGTOUCH_BOTTOM,
    }.get(data[0])
    logger.info("TOUCH %s: %r", TOUCH_CHARACTERISTIC_UUID, gesture)

    """only swipes implemented because the rest doesnt event work"""

    start_position = mouse.position
    swipe_amount = int(args.swipe_speed)
    if gesture == Gesture.SWIPE_LEFT:
        mouse.press(Button.left)
        mouse.move(-swipe_amount, 0)
        mouse.release(Button.left)
    elif gesture == Gesture.SWIPE_RIGHT:
        mouse.press(Button.left)
        mouse.move(swipe_amount, 0)
        mouse.release(Button.left)
    elif gesture == Gesture.SWIPE_UP:
        mouse.press(Button.left)
        mouse.move(0, -swipe_amount)
        mouse.release(Button.left)
    elif gesture == Gesture.SWIPE_DOWN:
        mouse.press(Button.left)
        mouse.move(0, swipe_amount)
        mouse.release(Button.left)

    # match gesture:
    #     case Gesture.SWIPE_LEFT:
    #         mouse.press(Button.left)
    #         mouse.move(-swipe_amount, 0)
    #         mouse.release(Button.left)
    #     case Gesture.SWIPE_RIGHT:
    #         mouse.press(Button.left)
    #         mouse.move(swipe_amount, 0)
    #         mouse.release(Button.left)
    #     case Gesture.SWIPE_UP:
    #         mouse.press(Button.left)
    #         mouse.move(0, -swipe_amount)
    #         mouse.release(Button.left)
    #     case Gesture.SWIPE_DOWN:
    #         mouse.press(Button.left)
    #         mouse.move(0, swipe_amount)
    #         mouse.release(Button.left)

    mouse.position = start_position


async def rotation_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    rotation_value = data[0] + (data[1] << 8)
    if (data[1] >> 7) > 0:
        rotation_value -= 1 << 16
    logger.info("ROTATION %s %r: %r", ROTATION_CHARACTERISTIC_UUID, Gesture.ROTATION,
                rotation_value)
    mouse.scroll(0, rotation_value * float(args.rotate_speed))


async def battery_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    logger.info("BATTERY %s %r: %r", BATTERY_CHARACTERISTIC_UUID, Gesture.BATTERY_LEVEL,
                int(binascii.hexlify(data), 16))


async def characteristic_value_updated(characteristic, value):
    logger.info("%s: %r", characteristic, value)
    await ({
        BUTTON_CHARACTERISTIC_UUID: button_handler,
        TOUCH_CHARACTERISTIC_UUID: touch_handler,
        ROTATION_CHARACTERISTIC_UUID: rotation_handler,
        # FLY_CHARACTERISTIC_UUID: ,
        BATTERY_CHARACTERISTIC_UUID: battery_handler,
    }[characteristic.uuid](characteristic, value))


async def main():
    logger.info("starting scan...")

    if args.address:
        device = await BleakScanner.find_device_by_address(
            args.address, cb=dict(use_bdaddr=args.macos_use_bdaddr)
        )
        if device is None:
            logger.error(
                "could not find device with address '%s'", args.address)
            return
    else:
        device = await BleakScanner.find_device_by_name(
            args.name, cb=dict(use_bdaddr=args.macos_use_bdaddr)
        )
        if device is None:
            logger.error("could not find device with name '%s'", args.name)
            return

    logger.info("connecting to device...")

    async with BleakClient(
        device,
        services=args.services,
    ) as client:
        logger.info("connected")

        for service in client.services:
            logger.info("[Service] %s", service)

            for char in service.characteristics:
                if "notify" in char.properties:
                    try:
                        await client.start_notify(char, characteristic_value_updated)
                        logger.info(
                            "  [Characteristic] %s (%s), Notify",
                            char,
                            ",".join(char.properties)
                        )
                    except Exception as e:
                        logger.error(
                            "  [Characteristic] %s (%s), Error: %s",
                            char,
                            ",".join(char.properties),
                            e,
                        )
                elif "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        logger.info(
                            "  [Characteristic] %s (%s), Value: %r",
                            char,
                            ",".join(char.properties),
                            value,
                        )
                    except Exception as e:
                        logger.error(
                            "  [Characteristic] %s (%s), Error: %s",
                            char,
                            ",".join(char.properties),
                            e,
                        )
                else:
                    logger.info(
                        "  [Characteristic] %s (%s)", char, ",".join(
                            char.properties)
                    )

                for descriptor in char.descriptors:
                    try:
                        value = await client.read_gatt_descriptor(descriptor.handle)
                        logger.info(
                            "    [Descriptor] %s, Value: %r", descriptor, value)
                    except Exception as e:
                        logger.error(
                            "    [Descriptor] %s, Error: %s", descriptor, e)
        while True:
            await asyncio.sleep(0.05)
        # logger.info("disconnecting...")

    # logger.info("disconnected")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    device_group = parser.add_mutually_exclusive_group(required=True)

    device_group.add_argument(
        "--name",
        metavar="<name>",
        help="the name of the bluetooth device to connect to",
    )
    device_group.add_argument(
        "--address",
        metavar="<address>",
        help="the address of the bluetooth device to connect to",
    )

    parser.add_argument(
        "--macos-use-bdaddr",
        action="store_true",
        help="when true use Bluetooth address instead of UUID on macOS",
    )

    parser.add_argument(
        "--services",
        nargs="+",
        metavar="<uuid>",
        help="if provided, only enumerate matching service(s)",
    )

    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="sets the log level to debug",
    )

    parser.add_argument(
        "-s",
        "--swipe_speed",
        metavar="<swipe_speed>",
        help="set the swipe speed"
    )

    parser.add_argument(
        "-r",
        "--rotate_speed",
        metavar="<rotate_speed>",
        help="set rotation speed"
    )

    global args
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    asyncio.run(main())
