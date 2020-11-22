#!/usr/bin/env python3

import asyncio
import logging

import co2meter as co2

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def publish_ubidots(token, **kwargs):
    domain = 'things.ubidots.com'
    url_tpl = '/api/v1.6/collections/values/?token={}'
    url = url_tpl.format(token)
    logger.info('Publish data ubidots: {}'.format(url))

    ubidots_map = (
        ('co2_ppm', config.UBIDOTS_CO2_ID),
        ('temperature', config.UBIDOTS_TEMPERATURE_ID),
    )

    reader, writer = await asyncio.open_connection(domain, 80)
    json_data = '[{}]'.format(','.join(
        '{{"variable": "{}", "value": {}}}'.format(ubidots_id, kwargs[var_name])
        for var_name, ubidots_id in ubidots_map
    ))
    query = \
        "POST {} HTTP/1.0\r\n" \
        "Host: things.ubidots.com\r\n" \
        "Content-Type: application/json\r\n" \
        "Content-Length: {}" \
        "\r\n\r\n{}".format(
            url,
            len(json_data.encode('latin-1')),
            json_data,
        )
    try:
        writer.write(query.encode('latin-1'))
        while True:
            line = await reader.readline()
            if not line:
                break
    except asyncio.TimeoutError:
        logger.error('publish_ubidots got timeout')
    finally:
        writer.close()


async def publish_thingspeak(api_key, **kwargs):
    thingspeak_map = (
        ('co2_ppm', config.THINGSPEAK_CO2_ID),
        ('temperature', config.THINGSPEAK_TEMPERATURE_ID),
    )

    domain = 'api.thingspeak.com'
    url_tpl = '/update?api_key={api_key}&{data}'
    url = url_tpl.format(
        api_key=api_key,
        data='&'.join(
            '{}={}'.format(field_id, kwargs[var_name])
            for var_name, field_id in thingspeak_map
        )
    )
    logger.info('Publish data thingspeak: {}'.format(url))

    reader, writer = await asyncio.open_connection(domain, 80)
    query = \
        "GET {} HTTP/1.0\r\n" \
        "Host: {}\r\n\r\n".format(
            url,
            domain,
        )
    try:
        writer.write(query.encode('latin-1'))
        while True:
            line = await reader.readline()
            if not line:
                break
    except asyncio.TimeoutError:
        logger.error('publish_thingspeak got timeout')
    finally:
        writer.close()


async def periodic_publish(*, ubidots_token, thingspeak_key, delay=20):
    while True:
        try:
            await publish_data(
                ubidots_token=ubidots_token,
                thingspeak_key=thingspeak_key,
            )
        except OSError as e:
            # skip socket.gaierror, try later
            logging.exception(str(e))
        await asyncio.sleep(delay)


async def publish_data(*, ubidots_token=None, thingspeak_key=None):
    mon = co2.CO2monitor()
    dt, co2_ppm, temp = mon.read_data()
    params = dict(
        co2_ppm='{0:d}'.format(co2_ppm),
        temperature='{0:.2f}'.format(temp),
    )
    if ubidots_token:
        await publish_ubidots(
            ubidots_token,
            **params,
        )
    if thingspeak_key:
        await publish_thingspeak(
            thingspeak_key,
            **params,
        )


async def shutdown():
    logger.info('Shutdown is running.')  # Happens in both cases
    await asyncio.sleep(1)
    logger.info('done')


def main():
    logger.setLevel(logging.DEBUG)
    loop = asyncio.get_event_loop()
    try:
        loop.create_task(periodic_publish(
            ubidots_token=config.UBIDOTS_TOKEN,
            thingspeak_key=config.THINGSPEAK_KEY,
        ))
        loop.run_forever()
    except KeyboardInterrupt:
        logger.warning('Keyboard interrupt at loop level.')
        loop.run_until_complete(shutdown())
    except Exception:
        loop.run_until_complete(shutdown())
        raise
    finally:
        loop.close()


if __name__ == '__main__':
    main()

