"""Main Program, for Testing Mainly"""
import argparse
import asyncio
import getpass

from aiohttp import ClientSession

from masterthermconnect.__version__ import __version__
from masterthermconnect.controller import MasterthermController
from masterthermconnect.exceptions import MasterthermError


def get_arguments() -> argparse.Namespace:
    """Read the Arguments passed in."""
    # formatter_class=argparse.MetavarTypeHelpFormatter,
    parser = argparse.ArgumentParser(
        prog="masterthermconnect",
        description="Python Mastertherm Connect API Module, used for debug purposes",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="Mastertherm Connect API Version: " + __version__,
        help="display the Mastertherm Connect API version",
    )
    parser.add_argument(
        "--api-ver",
        type=str,
        choices=["v1", "v2"],
        default="v1",
        help="API Version to use: Default: v1 (pre 2022), v2 (post 2022)",
    )
    parser.add_argument(
        "--hide-sensitive",
        action="store_true",
        help="Hide the actual sensitive information, "
        + "used when creating debug information for sharing.",
    )
    parser.add_argument("--user", type=str, help="login user for Mastertherm")
    parser.add_argument("--password", type=str, help="login password for Mastertherm")

    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="list the devices connected to the account",
    )
    parser.add_argument(
        "--list-device-data",
        action="store_true",
        help="list the data for each device connected to the account",
    )
    parser.add_argument(
        "--list-device-reg",
        action="store_true",
        help="list the raw registers for each device",
    )

    arguments = parser.parse_args()
    return arguments


async def connect(
    username: str, password: str, api_version: str, refresh: bool
) -> MasterthermController:
    """Setup and Connect to the Mastertherm Server."""
    # Login to the Server.
    session = ClientSession()
    controller = MasterthermController(
        username, password, session, api_version=api_version
    )

    try:
        await controller.connect()
        await controller.refresh_info()

        if refresh:
            await controller.refresh_data()

        return controller
    except MasterthermError as mte:
        print("Connection Failed " + mte.message)
    finally:
        await session.close()

    return None


def main() -> int:
    """Allow for some testing of connections from Command Line."""
    login_user = ""
    login_pass = ""
    args = get_arguments()

    if args.user is not None:
        login_user = args.user
    else:
        login_user = input("User: ")

    if args.password is not None:
        login_pass = args.password
    else:
        login_pass = getpass.getpass()

    refresh = args.list_device_data or args.list_device_registers
    controller = asyncio.run(connect(login_user, login_pass, args.api_ver, refresh))

    if args.list_devices:
        devices = controller.get_devices()
        new_module_id = 1111
        old_module_id = ""
        for device_id, device_item in devices.items():
            module_id = device_item["module_id"]
            unit_id = device_item["unit_id"]

            if module_id != old_module_id:
                old_module_id = module_id
                new_module_id = new_module_id + 1

            if args.hide_sensitive:
                device_id = f"{str(new_module_id)}_{unit_id}"
                device_item["module_id"] = str(new_module_id)
                device_item["module_name"] = "Hidden Name"
                device_item["name"] = "First"
                device_item["surname"] = "Last"
                device_item["latitude"] = "1.1"
                device_item["longitude"] = "-0.1"

            print(device_id + ": " + str(device_item))

    if args.list_device_data:
        devices = controller.get_devices()
        new_module_id = 1111
        old_module_id = ""
        for device_id, device_item in devices.items():
            module_id = device_item["module_id"]
            unit_id = device_item["unit_id"]

            device_data = controller.get_device_data(module_id, unit_id)
            if module_id != old_module_id:
                old_module_id = module_id
                new_module_id = new_module_id + 1

            if args.hide_sensitive:
                device_id = f"{str(new_module_id)}_{unit_id}"

            print(device_id + ": " + str(device_data))

    if args.list_device_reg:
        devices = controller.get_devices()
        new_module_id = 1111
        old_module_id = ""
        for device_id, device_item in devices.items():
            module_id = device_item["module_id"]
            unit_id = device_item["unit_id"]

            device_reg = controller.get_device_registers(module_id, unit_id)
            if module_id != old_module_id:
                old_module_id = module_id
                new_module_id = new_module_id + 1

            if args.hide_sensitive:
                device_id = f"{str(new_module_id)}_{unit_id}"

            print(device_id + ": " + str(device_reg))

    return 0


if __name__ == "__main__":
    main()
