#! /bin/python
import sys
import os
import json
import asyncio
import aiohttp
import json
import requests
from datetime import datetime as dt
from discord_webhook import DiscordWebhook
conn = aiohttp.TCPConnector(limit_per_host=100, limit=0, ttl_dns_cache=300)
PARALLEL_REQUESTS = 100
results = [None]*30
headers ={
    'Referer': 'https://shifts.coop.co.uk/',
    'Content-Type': 'application/json',
    'Origin': 'https://shifts.coop.co.uk',
    'Authorization': os.getenv("COOPSHIFTTOKEN"),
}
url = "https://api.shifts.coop.co.uk/rota/5343/management/daily"
async def gather_with_concurrency(n):
    semaphore = asyncio.Semaphore(n)
    session = aiohttp.ClientSession(connector=conn)
    async def get(url,headers,offset):
        async with semaphore:
            async with session.get(url,params={'offset':str(offset)},headers=headers) as response:
                obj = json.loads(await response.read())
                ret = {}
                date = obj["date"]
                for row in obj["items"]:
                    # if row['item_type'] != "Shift" or row['is_home_store_shift']=="False":
                    if row['item_type'] != "Shift":
                        continue
                    times = (row["scheduled_start_time"],row["scheduled_end_time"])
                    ret[date+" - "+row['colleague_name'].split(" ")[0]]= " - ".join(dt.fromisoformat(a).strftime("%H:%M") for a in times)
                results[offset]=ret
    await asyncio.gather(*(get(url,headers,offset) for offset in range(22)))
    await session.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(gather_with_concurrency(PARALLEL_REQUESTS))
conn.close()
newcal={}
for item in results:
    if item!=None:
        newcal|=item

yourShifts=[]
for shift in newcal.keys():
    if "Dexter" in shift:
        yourShifts.append(shift + "- " + newcal[shift]+"\n")


bigChannel=os.getenv("DISCORDCOOP")
myChannel=os.getenv("DISCORDCOOPUPDATE")
with open("/home/dex/.cache/shifts/lastRecorded.json","w") as file:
    json.dump(newcal,file)

try:
    with open("/home/dex/.cache/shifts/lastRecorded.json","r") as prev:
        oldcal=json.load(prev)
except:
    print("reading error")
    oldcal={}
message=[]

for deletion in (oldcal.keys()-newcal.keys()):
    message.append("D "+ deletion+" " + oldcal[deletion]+"\n")

for shift,times in newcal.items():
    if shift in oldcal.keys():
        if times!=oldcal[shift]:
            message.append("U "+shift+" "+oldcal[shift]+" -> "+times+"\n")
            # print("U ",shift," ",oldcal[shift]," -> ",times)
    else:
        message.append("A "+shift+" "+times+"\n")
        # print("A ",shift," ",times)

if message!=[]:
    message=["NEW NOTIFICATION\n"]+message
    buffer=""
    i=0
    while i < len(message):
        while  i < len(message) and len(buffer)+len(message[i])<2000:
            buffer+=message[i]
            i+=1
        webhook = DiscordWebhook(url=bigChannel, username="shifts",content=buffer)
        response = webhook.execute()
        buffer=""
    buffer=""
    i=0
    while i < len(yourShifts):
        while  i < len(yourShifts) and len(buffer)+len(yourShifts[i])<2000:
            buffer+=yourShifts[i]
            i+=1
        webhook = DiscordWebhook(url=myChannel, username="shifts",content=buffer)
        response = webhook.execute()
        buffer=""
