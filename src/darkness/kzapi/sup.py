from typing import NotRequired, Optional, TypedDict

from fabric import Connection, transfer

import os
import uuid
import time


class HostDescriptionShort(TypedDict):
    host: str
    user: NotRequired[str]
    port: NotRequired[int]
    connect_kwargs: NotRequired[dict]


class HostDescription(HostDescriptionShort):
    gateway: NotRequired[HostDescriptionShort]


class Job(TypedDict):
    id: str
    command: str
    name: str
    files_to_upload: NotRequired[list[str]]
    files_to_download: NotRequired[list[str]]


class Sup:
    def __init__(self, environment):
        self.environment = environment
        self.remote_runner = RemoteRunner(self.environment)

    def __call__(self, *args, **kwargs):
        command = "/opt/kazoo/bin/sup " + " ".join(args)
        print('__call__', self.environment['host'], " ".join(args))
        return self.remote_runner.run_command(command)
        #return self.crossbar.api_request(self.suburl, *args, **kwargs)

    def __enter__(self):
        self.remote_runner.connection()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class RemoteRunner:
    def __init__(self, host: HostDescription):
        self.host = host
        self.job: Optional[Job] = None
        self.__connection: Optional[Connection] = None
        self.__gateway: Optional[Connection] = None
        self.__transfer: Optional[transfer.Transfer] = None
        self.__current_dir: Optional[str] = None

    def connection(self) -> Connection:
        if not self.__connection:
            if 'gateway' in self.host:
                self.__gateway = Connection(**(self.host['gateway']))

            self.__connection = Connection(**(self.host))


        return self.__connection

    def transfer(self) -> transfer.Transfer:
        if not self.__transfer:
            self.__transfer = transfer.Transfer(self.connection())

        return self.__transfer

    def current_dir(self) -> str:
        if not self.__current_dir:
            self.__current_dir = self.run_command("pwd")

        return self.__current_dir

    def run(self, job: Job):
        self.job = job
        result = False
        try:
            self.init_job()
            result = self.perform_job()
        except Exception as err:
            print(f"Failed to run SSH command: {err}")
            return False
        finally:
            self.shutdown_job()

        return result

    def run_command(self, command) -> str:
        result = self.connection().run(command, hide=True)

        if not result.ok:
            raise Exception(f"Error {result.error} while running SSH command '{command}', output:\n {result.output}")
        return result.stdout.strip()

    def working_dir(self):
        if not self.job: raise Exception("No Job running")

        self.connection()
        return f"{self.current_dir()}/job_{self.job['id']}"

    def init_job(self):
        if not self.job: raise Exception("No Job running")

        self.run_command(f"mkdir -p '{self.working_dir()}'")
        self.run_command(f"cd '{self.working_dir()}'")
        if 'files_to_upload' in self.job:
            for job_file in self.job['files_to_upload']:
                self.transfer().put(job_file, self.working_dir())

    def perform_job(self):
        if not self.job: raise Exception("No Job running")

        command = f'cd {self.working_dir()} && {self.job["command"]}'
        result = self.run_command(command)

        name = ''
        local_dir = f'{self.job["name"]}/{self.job["id"]}/{self.host["host"]}'
        if 'files_to_download' in self.job:
            os.makedirs(local_dir)
            for job_file in self.job['files_to_download']:
                self.transfer().get(f'{self.working_dir()}/{job_file}', f'{local_dir}/{job_file}')

        return result

    def shutdown_job(self):
        if not self.job: raise Exception("No Job running")

        self.run_command(f"rm -rf '{self.working_dir()}'")

    pass
