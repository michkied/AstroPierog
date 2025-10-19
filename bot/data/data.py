import json
import os
import pathlib

import aiofiles
import asyncio

from bot.entities import *

lock = asyncio.Lock()
path = str(pathlib.Path(__file__).parent.absolute())


class Data:
    def __init__(self):
        self.coordinators = {}  # key: coordinator ID, value: Coordinator object
        self.recruits = {}  # key: recruit ID, value: Recruit object

    async def store(self):
        data = json.dumps({
            'coordinators': {str(k): v.to_dict() for k, v in self.coordinators.items()}
        }, ensure_ascii=False, indent=4)
        async with lock:
            async with aiofiles.open(os.path.join(path, 'data.json'), 'w+') as f:
                await f.write(data)

    def load(self):
        try:
            with open(os.path.join(path, 'data.json'), 'r', encoding='UTF-8') as f:
                data = json.load(f)

            for coord_id, coord_data in data.get('coordinators', {}).items():
                coordinator = Coordinator(int(coord_id))
                for ts_data in coord_data.get('time_slots', []):
                    ts = TimeSlot(ts_data['date'], ts_data['hour'])
                    coordinator.time_slots.append(ts)
                    if ts_data['recruit_id'] is not None:
                        recruit_id = ts_data['recruit_id']
                        if recruit_id not in self.recruits:
                            self.recruits[recruit_id] = Recruit(recruit_id)
                        ts.book(self.recruits[recruit_id], coordinator)
                self.coordinators[int(coord_id)] = coordinator
        except FileNotFoundError:
            pass
