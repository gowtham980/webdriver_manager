import datetime
import json
import os

from webdriver_manager.core.config import wdm_local, get_xdist_worker_id
from webdriver_manager.core.constants import (
    DEFAULT_PROJECT_ROOT_CACHE_PATH,
    DEFAULT_USER_HOME_CACHE_PATH, ROOT_FOLDER_NAME,
)
from webdriver_manager.core.logger import log
from webdriver_manager.core.utils import get_date_diff, File, save_file, format_version


class DriverCache(object):
    def __init__(self, root_dir=None, valid_range=1):
        self._root_dir = DEFAULT_USER_HOME_CACHE_PATH
        is_wdm_local = wdm_local()
        xdist_worker_id = get_xdist_worker_id()
        if xdist_worker_id:
            log(f"xdist worker is: {xdist_worker_id}")
            self._root_dir = os.path.join(self._root_dir, xdist_worker_id)

        if root_dir is not None:
            self._root_dir = os.path.join(root_dir, ROOT_FOLDER_NAME, xdist_worker_id)
        if is_wdm_local:
            self._root_dir = os.path.join(DEFAULT_PROJECT_ROOT_CACHE_PATH, xdist_worker_id)

        self._drivers_root = "drivers"
        self._drivers_json_path = os.path.join(self._root_dir, "drivers.json")
        self._date_format = "%d/%m/%Y"
        self._drivers_directory = os.path.join(self._root_dir, self._drivers_root)
        self.valid_range = valid_range

    def save_file_to_cache(self, driver, file: File):
        driver_name = driver.get_name()
        os_type = driver.get_os_type()
        driver_version = driver.get_version()
        browser_version = driver.get_browser_version()
        browser_type = driver.get_browser_type()
        unified_version = format_version(browser_type, driver_version)

        path = os.path.join(
            self._drivers_directory, driver_name, os_type, unified_version
        )
        archive = save_file(file, path)
        files = archive.unpack(path)
        binary = self.__get_binary(files, driver_name)
        binary_path = os.path.join(path, binary)
        self.__save_metadata(
            browser_version, driver_name, os_type, unified_version, binary_path
        )
        log(f"Driver has been saved in cache [{path}]")
        return binary_path

    def __get_binary(self, files, driver_name):
        if len(files) == 1:
            return files[0]

        for f in files:
            if driver_name in f:
                return f

        raise Exception(f"Can't find binary for {driver_name} among {files}")

    def __save_metadata(
            self,
            browser_version,
            driver_name,
            os_type,
            driver_version,
            binary_path,
            date=None,
    ):
        if date is None:
            date = datetime.date.today()

        metadata = self.get_metadata()

        key = f"{os_type}_{driver_name}_{driver_version}_for_{browser_version}"

        data = {
            key: {
                "timestamp": date.strftime(self._date_format),
                "binary_path": binary_path,
            }
        }

        metadata.update(data)
        with open(self._drivers_json_path, "w+") as outfile:
            json.dump(metadata, outfile, indent=4)

    def find_driver(self, driver):
        """Find driver by '{os_type}_{driver_name}_{driver_version}_{browser_version}'."""
        os_type = driver.get_os_type()
        driver_name = driver.get_name()
        driver_version = driver.get_version()
        browser_version = driver.get_browser_version()
        browser_type = driver.get_browser_type()
        unified_version = format_version(browser_type, driver_version)

        metadata = self.get_metadata()

        key = f"{os_type}_{driver_name}_{unified_version}_for_{browser_version}"
        if key not in metadata:
            log(
                f"There is no [{os_type}] {driver_name} for browser {browser_version} in cache"
            )
            return None

        path = os.path.join(self._drivers_directory, driver_name, os_type, unified_version)

        driver_binary_name = driver.get_binary_name()
        binary_path = os.path.join(path, driver_binary_name)
        if not os.path.exists(binary_path):
            return None

        driver_info = metadata[key]

        if not self.__is_valid(driver_info):
            return None

        path = driver_info["binary_path"]
        log(f"Driver [{path}] found in cache")
        return path

    def __is_valid(self, driver_info):
        dates_diff = get_date_diff(
            driver_info["timestamp"], datetime.date.today(), self._date_format
        )
        return dates_diff < self.valid_range

    def get_metadata(self):
        if os.path.exists(self._drivers_json_path):
            try:
                with open(self._drivers_json_path, "r") as outfile:
                    return json.load(outfile)
            except Exception as e:
                log(f"Driver json error {e}")
        return {}
