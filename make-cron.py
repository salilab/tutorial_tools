#!/usr/bin/python3

import sys
import random

minute = random.randint(0, 59)
hour = random.randint(0, 23)
weekday = random.randint(0, 6)

print('"%d %d * * %d"  # Run at a random time weekly' % (minute, hour, weekday))
