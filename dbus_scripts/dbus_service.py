import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
import subprocess

class PermissionService(dbus.service.Object):
    def __init__(self, bus_name, object_path='/org/example/PermissionService'):
        super().__init__(bus_name, object_path)

    @dbus.service.method('org.example.PermissionService', in_signature='s', out_signature='b')
    def RequestPermission(self, message):
        print(f"Permission requested for: {message}")
        return self.show_popup(message)

    def show_popup(self, message):
        command = ['zenity', '--question', '--text', message]
        try:
            subprocess.check_call(command)
            return True  # Access granted
        except subprocess.CalledProcessError:
            return False  # Access denied


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()
    bus_name = dbus.service.BusName('org.example.PermissionService', session_bus)
    permission_service = PermissionService(bus_name)

    loop = GLib.MainLoop()
    print("Running D-Bus service...")
    loop.run()


if __name__ == '__main__':
    main()
