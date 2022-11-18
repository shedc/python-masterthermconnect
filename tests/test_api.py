"""Test the API Client."""
from datetime import datetime, timedelta
from hashlib import sha1
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, Request

import pytest

from masterthermconnect import (
    MasterthermAuthenticationError,
    MasterthermConnectionError,
    MasterthermTokenInvalid,
)
from masterthermconnect.api import MasterthermAPI
from masterthermconnect.const import (
    DATE_FORMAT,
    URL_BASE,
    URL_BASE_NEW,
    URL_LOGIN,
    URL_LOGIN_NEW,
    URL_MODULES_NEW,
    URL_PUMPDATA,
    URL_PUMPDATA_NEW,
    URL_PUMPINFO,
    URL_PUMPINFO_NEW,
)

from .conftest import GENERAL_ERROR_RESPONSE, VALID_LOGIN, load_fixture


@patch("masterthermconnect.api.URL_BASE", "")
class APITestCase(AioHTTPTestCase):
    """Test the Original API Connection"""

    logged_in = True

    async def get_application(self):
        """Start and Return a mock application."""

        async def _connect_response(request: Request):
            """Check the Test Login Credentials and return login connect or failure."""
            data = await request.post()
            password = sha1(VALID_LOGIN["upwd"].encode("utf-8")).hexdigest()
            if data["uname"] == VALID_LOGIN["uname"] and data["upwd"] == password:
                response_text = load_fixture("login_success.json")
            else:
                response_text = load_fixture("login_invalid.json")

            token_expires = datetime.now() + timedelta(seconds=60)
            response = web.Response(
                text=response_text,
                content_type="application/json",
            )
            response.set_cookie(
                "PHPSESSID",
                VALID_LOGIN["token"],
                expires=token_expires.strftime(DATE_FORMAT) + "GMT",
            )

            self.logged_in = True
            return response

        async def _get_info(request: Request):
            """Get the Pump Info."""
            data = await request.post()
            if not self.logged_in:
                response_text = GENERAL_ERROR_RESPONSE
            else:
                module_id = data["moduleid"]
                unit_id = data["unitid"]
                response_text = load_fixture(f"pumpinfo_{module_id}_{unit_id}.json")
                if response_text is None:
                    response_text = load_fixture("pumpinfo_invalid.json")

            response = web.Response(text=response_text, content_type="application/json")
            return response

        async def _get_data(request: Request):
            """Get the Pump Info."""
            data = await request.post()
            module_id = data["moduleId"]
            unit_id = data["deviceId"]
            last_update_time = data["lastUpdateTime"]

            if not self.logged_in:
                response_text = load_fixture("pumpdata_unavailable.json")
            else:
                response_text = load_fixture(
                    f"pumpdata_{module_id}_{unit_id}_{last_update_time}.json"
                )
                if response_text is None:
                    response_text = load_fixture("pumpdata_invalid.json")

            response = web.Response(text=response_text, content_type="application/json")
            return response

        app = web.Application()
        app.router.add_post(URL_LOGIN, _connect_response)
        app.router.add_post(URL_PUMPINFO, _get_info)
        app.router.add_post(URL_PUMPDATA, _get_data)
        return app

    async def test_setup(self):
        """Test the API Setup."""
        assert MasterthermAPI(VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client)

    async def test_connect(self):
        """Test the API Logs in and Returns modules."""
        api = MasterthermAPI(VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client)
        result = await api.connect()

        assert result != {}
        assert result["returncode"] == 0
        assert result["modules"][0]["id"] == "1234"
        assert result["role"] == "400"

    async def test_autherror(self):
        """Test a Connection Authentication Error."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"] + "bad", self.client
        )

        with pytest.raises(MasterthermAuthenticationError):
            await api.connect()

    async def test_connecterror(self):
        """Test the Connection Invalid Error."""
        api = MasterthermAPI(VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client)

        with patch("masterthermconnect.api.URL_LOGIN", "/"), pytest.raises(
            MasterthermConnectionError
        ):
            await api.connect()

    async def test_getinfo(self):
        """Test returning the Device Information."""
        api = MasterthermAPI(VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client)
        assert await api.connect() != {}

        info = await api.get_device_info("1234", "1")

        assert info != {}
        assert info["moduleid"] == "1234"
        assert info["type"] == "AQI"

    async def test_getinfo_notconnected(self):
        """Test the get device info when not connected."""
        api = MasterthermAPI(VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client)
        assert await api.connect() is not {}

        self.logged_in = False
        with pytest.raises(MasterthermTokenInvalid):
            await api.get_device_info("1234", "1")

    async def test_getinfo_invalid(self):
        """Test the device info for invalid device."""
        api = MasterthermAPI(VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client)
        assert await api.connect() is not {}
        info = await api.get_device_info("1234", "2")

        assert info["returncode"] != 0

    async def test_getdata(self):
        """Test the Get Device data from new."""
        api = MasterthermAPI(VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client)
        assert await api.connect() is not {}

        data = await api.get_device_data("1234", "1")

        assert data != {}
        assert data["error"]["errorId"] == 0
        assert data["messageId"] == 1
        assert data["data"] != {}

    async def test_getdata_update(self):
        """Test the Get device Data update."""
        api = MasterthermAPI(VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client)
        assert await api.connect() is not {}

        data = await api.get_device_data("1234", "1")
        assert data != {}

        last_update_time = data["timestamp"]
        a_500 = data["data"]["varFileData"]["001"]["A_500"]

        data = await api.get_device_data("1234", "1", last_update_time=last_update_time)
        assert data != {}
        assert data["error"]["errorId"] == 0
        assert data["timestamp"] != last_update_time
        assert data["data"]["varFileData"]["001"]["A_500"] != a_500

    async def test_getdata_invalid(self):
        """Test the get invalid device."""
        api = MasterthermAPI(VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client)
        assert await api.connect() is not {}

        data = await api.get_device_data("1234", "2")
        assert data != {}
        assert data["error"]["errorId"] != 0

    async def test_getdata_unavailable(self):
        """Test getting data when the device is not available."""
        api = MasterthermAPI(VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client)
        assert await api.connect() is not {}

        self.logged_in = False

        data = await api.get_device_data("1234", "1")
        assert data != {}
        assert data["error"]["errorId"] == 9


@patch("masterthermconnect.api.URL_BASE_NEW", "")
class APINewTestCase(AioHTTPTestCase):
    """Test the New API Connection"""

    logged_in = True

    async def get_application(self):
        """Start and Return a mock application."""

        async def _connect_response(request: Request):
            """Check the Test Login Credentials and return login connect or failure."""
            data = await request.post()
            if (
                data["username"] == VALID_LOGIN["uname"]
                and data["password"] == VALID_LOGIN["upwd"]
            ):
                response_text = load_fixture("newapi/login_success.json")
            else:
                response_text = load_fixture("newapi/login_invalid.json")

            response = web.Response(
                text=response_text,
                content_type="application/json",
            )

            self.logged_in = True
            return response

        async def _get_modules(request: Request):
            """Get the Devices, new in the new API."""
            token = request.headers.get("Authorization")
            if token != "Bearer bearertoken":
                response_text = load_fixture("newapi/module_failure.json")

            if not self.logged_in:
                response_text = load_fixture("newapi/module_failure.json")
            else:
                response_text = load_fixture("newapi/modules.json")

            if response_text is None:
                response_text = GENERAL_ERROR_RESPONSE

            response = web.Response(text=response_text, content_type="application/json")
            return response

        async def _get_info(request: Request):
            """Get the Pump Info."""
            token = request.headers.get("Authorization")
            if token != "Bearer bearertoken":
                response_text = load_fixture("pumpinfo_invalid.json")

            data = request.query
            if not self.logged_in:
                response_text = GENERAL_ERROR_RESPONSE
            else:
                module_id = data["moduleid"]
                unit_id = data["unitid"]
                response_text = load_fixture(
                    f"newapi/pumpinfo_{module_id}_{unit_id}.json"
                )
                if response_text is None:
                    response_text = load_fixture("pumpinfo_invalid.json")

            response = web.Response(text=response_text, content_type="application/json")
            return response

        async def _get_data(request: Request):
            """Get the Pump Info."""
            token = request.headers.get("Authorization")
            if token != "Bearer bearertoken":
                response_text = load_fixture("pumpinfo_invalid.json")

            data = request.query

            module_id = data["moduleId"]
            unit_id = data["deviceId"]
            last_update_time = data["lastUpdateTime"]

            if not self.logged_in:
                response_text = load_fixture("pumpdata_unavailable.json")
            else:
                response_text = load_fixture(
                    f"newapi/pumpdata_{module_id}_{unit_id}_{last_update_time}.json"
                )
                if response_text is None:
                    response_text = load_fixture("pumpdata_invalid.json")

            response = web.Response(text=response_text, content_type="application/json")
            return response

        app: web.Application = web.Application()
        app.router.add_post(URL_LOGIN_NEW, _connect_response)
        app.router.add_get(URL_MODULES_NEW, _get_modules)
        app.router.add_get(URL_PUMPINFO_NEW, _get_info)
        app.router.add_get(URL_PUMPDATA_NEW, _get_data)
        return app

    async def test_setup(self):
        """Test the API Setup."""
        assert MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client, original_api=False
        )

    async def test_connect(self):
        """Test the API Logs in and Returns modules."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client, original_api=False
        )
        result = await api.connect()

        assert result != {}
        assert result["returncode"] == 0
        assert result["modules"][0]["id"] == "10021"
        assert result["role"] == "400"

    async def test_autherror(self):
        """Test a Connection Authentication Error."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"],
            VALID_LOGIN["upwd"] + "bad",
            self.client,
            original_api=False,
        )

        with pytest.raises(MasterthermAuthenticationError):
            await api.connect()

    async def test_connecterror(self):
        """Test the Connection Invalid Error."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client, original_api=False
        )

        with patch("masterthermconnect.api.URL_LOGIN_NEW", "/"), pytest.raises(
            MasterthermConnectionError
        ):
            await api.connect()

    async def test_getinfo(self):
        """Test returning the Device Information."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client, original_api=False
        )
        assert await api.connect() != {}

        info = await api.get_device_info("10021", "1")

        assert info != {}
        assert info["moduleid"] == 10021
        assert info["type"] == "BAI"

    async def test_getinfo_notconnected(self):
        """Test the get device info when not connected."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client, original_api=False
        )
        assert await api.connect() is not {}

        self.logged_in = False
        with pytest.raises(MasterthermTokenInvalid):
            await api.get_device_info("10021", "1")

    async def test_getinfo_invalid(self):
        """Test the device info for invalid device."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client, original_api=False
        )
        assert await api.connect() is not {}
        info = await api.get_device_info("1234", "2")

        assert info["returncode"] != 0

    async def test_getdata(self):
        """Test the Get Device data from new."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client, original_api=False
        )
        assert await api.connect() is not {}

        data = await api.get_device_data("10021", "1")

        assert data != {}
        assert data["error"]["errorId"] == 0
        assert data["messageId"] == 1
        assert data["data"] != {}

    async def test_getdata_update(self):
        """Test the Get device Data update."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client, original_api=False
        )
        assert await api.connect() is not {}

        data = await api.get_device_data("10021", "1")
        assert data != {}

        last_update_time = data["timestamp"]
        a_500 = data["data"]["varFileData"]["001"]["A_500"]

        data = await api.get_device_data(
            "10021", "1", last_update_time=last_update_time
        )
        assert data != {}
        assert data["error"]["errorId"] == 0
        assert data["timestamp"] != last_update_time
        assert data["data"]["varFileData"]["001"]["A_500"] != a_500

    async def test_getdata_invalid(self):
        """Test the get invalid device."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client, original_api=False
        )
        assert await api.connect() is not {}

        data = await api.get_device_data("1234", "2")
        assert data != {}
        assert data["error"]["errorId"] != 0

    async def test_getdata_unavailable(self):
        """Test getting data when the device is not available."""
        api = MasterthermAPI(
            VALID_LOGIN["uname"], VALID_LOGIN["upwd"], self.client, original_api=False
        )
        assert await api.connect() is not {}

        self.logged_in = False

        data = await api.get_device_data("10021", "1")
        assert data != {}
        assert data["error"]["errorId"] == 9
