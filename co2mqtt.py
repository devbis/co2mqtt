#!/usr/bin/env python3

import asyncio
import json
import logging
from typing import Optional

import co2meter as co2
import aio_mqtt

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CarbonDioxideMQTT:
    def __init__(
            self,
            reconnection_interval: int = 10,
            loop: Optional[asyncio.AbstractEventLoop] = None
    ) -> None:
        self._reconnection_interval = reconnection_interval
        self._loop = loop or asyncio.get_event_loop()
        self._client = aio_mqtt.Client(loop=self._loop)
        self._tasks = [
            self._loop.create_task(self._connect_forever()),
            self._loop.create_task(self._periodic_publish())
        ]

        self._bypass_decrypt = False
        self._co2 = co2.CO2monitor(bypass_decrypt=self._bypass_decrypt)
        self.device_name = \
            f'{self._co2.info["product_name"]}_' \
            f'{self._co2.info["serial_no"].replace(".", "_")}'

        self.mqtt_prefix = f'homeassistant/sensor/{self.device_name}'

    async def close(self) -> None:
        for task in self._tasks:
            if task.done():
                continue
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if self._client.is_connected():
            await self._client.disconnect()

    async def _connect_forever(self) -> None:
        while True:
            try:
                connect_result = await self._client.connect(
                    host=config.MQTT_SERVER,
                    username=config.MQTT_USER,
                    password=config.MQTT_PASSWORD,
                )
                logger.info("Connected")

                print(f'{self.mqtt_prefix}/co2/config')

                device = {
                    "identifiers": [
                        self.device_name,
                    ],
                    "name": self.device_name,
                    "sw_version": self._co2.info["serial_no"],
                    "model": self.device_name,
                    "manufacturer": self._co2.info['manufacturer'],
                }

                await self._client.publish(
                    aio_mqtt.PublishableMessage(
                        topic_name=f'{self.mqtt_prefix}/co2/config',
                        payload=json.dumps({
                            'name': f'co2_{self.device_name}',
                            'unique_id': f'co2_{self.device_name}',
                            "state_topic": f"{self.mqtt_prefix}/sensor/state",
                            "unit_of_measurement": "ppm",
                            "value_template": "{{ value_json.co2 }}",
                            "device": device,
                        }),
                        qos=aio_mqtt.QOSLevel.QOS_1,
                        retain=True
                    )
                )
                await self._client.publish(
                    aio_mqtt.PublishableMessage(
                        topic_name=f'{self.mqtt_prefix}/temperature/config',
                        payload=json.dumps({
                            "device_class": "temperature",
                            'name': f'temperature_{self.device_name}',
                            'unique_id': f'temperature_{self.device_name}',
                            "state_topic": f"{self.mqtt_prefix}/sensor/state",
                            "unit_of_measurement": "\u00b0C",
                            "value_template": "{{ value_json.temperature }}",
                            "device": device,
                        }),
                        qos=aio_mqtt.QOSLevel.QOS_1,
                        retain=True
                    )
                )

                logger.info("Wait for network interruptions...")
                await connect_result.disconnect_reason
            except asyncio.CancelledError:
                raise

            except aio_mqtt.AccessRefusedError as e:
                logger.error("Access refused", exc_info=e)

            except (
                aio_mqtt.ConnectionLostError,
                aio_mqtt.ConnectionClosedError,
                aio_mqtt.ServerDiedError,
            ) as e:
                logger.error("Connection lost. Will retry in %d seconds", self._reconnection_interval, exc_info=e)
                await asyncio.sleep(self._reconnection_interval, loop=self._loop)

            except aio_mqtt.ConnectionCloseForcedError as e:
                logger.error("Connection close forced", exc_info=e)
                return

            except Exception as e:
                logger.error("Unhandled exception during connecting", exc_info=e)
                return

            else:
                logger.info("Disconnected")
                return

    def _read(self):
        dt, co2_ppm, temp = self._co2.read_data()
        if co2_ppm is None and temp is None:
            self._bypass_decrypt = not self._bypass_decrypt
            logger.warning(
                f'Fallback to read with bypass_decrypt={self._bypass_decrypt}',
            )
            self._co2 = co2.CO2monitor(bypass_decrypt=self._bypass_decrypt)
            dt, co2_ppm, temp = self._co2.read_data()
        return dt, co2_ppm, temp

    async def _read_and_publish(self):
        dt, co2_ppm, temp = self._read()
        await self._client.publish(
            aio_mqtt.PublishableMessage(
                topic_name=f"{self.mqtt_prefix}/sensor/state",
                payload=json.dumps({
                    'co2': co2_ppm,
                    'temperature': round(temp, 2),
                }),
                qos=aio_mqtt.QOSLevel.QOS_1
            )
        )

    async def _periodic_publish(self, period=10):
        while True:
            if not self._client.is_connected():
                await asyncio.sleep(1)
                continue
            try:
                await asyncio.wait_for(
                    self._read_and_publish(),
                    timeout=15,
                )
            except asyncio.TimeoutError:
                logger.exception("Read and publish timeout")
                continue
            except aio_mqtt.ConnectionClosedError as e:
                logger.exception("Connection closed")
                await self._client.wait_for_connect()
                continue

            except Exception:
                logger.exception(
                    "Unhandled exception during echo message publishing",
                )
            await asyncio.sleep(period)


async def shutdown():
    logger.info('Shutdown is running.')  # Happens in both cases
    await asyncio.sleep(1)
    logger.info('done')


def main():
    logging.basicConfig(
        level='DEBUG'
    )
    loop = asyncio.new_event_loop()
    server = CarbonDioxideMQTT(
        reconnection_interval=10,
        loop=loop,
    )
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.warning('Keyboard interrupt at loop level.')
    except Exception:
        loop.run_until_complete(shutdown())
        raise
    finally:
        loop.run_until_complete(server.close())
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == '__main__':
    main()

