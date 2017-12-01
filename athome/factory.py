# Copyright (c) 2017 Alessandro Duca
#
# See the file LICENCE for copying permission.

from athome.subsystem import hbmqtt, mqttbridge, http, plugins
import athomelib.locator as locator

def new(path):
    normalized = locator.normalize_path(path)
    func_name = normalized.replace('/', '_')
    return globals()[func_name]()
        
def subsystem_hbmqtt():
    return hbmqtt.Subsystem()