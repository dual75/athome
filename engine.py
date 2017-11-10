# Copyright (c) 2017,2017 Alessandro Duca <alessandro.duca@gmail.com>
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# 3. Neither the name of mosquitto nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import os, sys
import asyncio
import logging

import yaml

import athome

LOGGER = logging.getLogger(__name__)

config = yaml.load(open('config.yml', 'rb'))

def init_env():
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('hbmqtt').setLevel(logging.INFO)
    logging.getLogger('transitions').setLevel(logging.WARN)
    LOGGER.debug(sys.path)


init_env()
async def main(loop):
    LOGGER.info("in main(loop)")
    await asyncio.gather(
        athome.plugins.watch_plugin_dir(config['plugins'], loop),
        athome.mqtt.run_broker(config['hbmqtt'])
        )

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main(loop))
        result = 0
    except InterruptedException as ex:
        loop.run_until_complete(mqtt.stop_broker())
    except Exception as ex:
        LOGGER.exception(ex)
        result = -1
    finally:
        loop.stop()
        loop.close()
    sys.exit(result)

