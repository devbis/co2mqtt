#!/usr/bin/env python3

import asyncio
import logging

import co2meter as co2

import config

logger = logging.getLogger(__name__)


async def publish_ubidots(token, **kwargs):
    domain = 'things.ubidots.com'
    url_tpl = '/api/v1.6/collections/values/?token={}'
    url = url_tpl.format(token)
    logging.info('Publish data ubidots: {}'.format(url))

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
        logging.error('publish_ubidots got timeout')


async def periodic_publish(ubidots_token, delay=20):
    while True:
        try:
            await publish_data(ubidots_token)
        except OSError:
            # skip socket.gaierror, try later
            pass
        await asyncio.sleep(delay)


async def publish_data(ubidots_token=None):
    mon = co2.CO2monitor()
    dt, co2_ppm, temp = mon.read_data()
    await publish_ubidots(
        ubidots_token,
        co2_ppm='{0:d}'.format(co2_ppm),
        temperature='{0:.2f}'.format(temp),
    )


async def shutdown():
    logging.info('Shutdown is running.')  # Happens in both cases
    await asyncio.sleep(1)
    logging.info('done')


def main():
    loop = asyncio.get_event_loop()
    try:
        loop.create_task(periodic_publish(
            ubidots_token=config.UBIDOTS_TOKEN,
        ))
        loop.run_forever()
    except KeyboardInterrupt:
        logging.warning('Keyboard interrupt at loop level.')
        loop.run_until_complete(shutdown())
    finally:
        loop.close()


if __name__ == '__main__':
    main()

