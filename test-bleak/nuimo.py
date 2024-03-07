import asyncio
from bleak import BleakClient

address = "0E:BE:0E:C4:DD:A4"
MODEL_NBR_UUID = "2A24"

async def main(address):
    async with BleakClient(address) as client:
        model_number = await client.read_gatt_char(MODEL_NBR_UUID)
        print("Model Number: {0}".format("".join(map(chr, model_number))))

asyncio.run(main(address))