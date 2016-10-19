from nats.aio.utils import hex_rand


def create_guid():
    return ''.join([hex_rand(0x10),
                    hex_rand(0x10),
                    hex_rand(0x10),
                    hex_rand(0x10),
                    hex_rand(0x24)])