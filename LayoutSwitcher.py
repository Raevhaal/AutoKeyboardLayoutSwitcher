# using pywin32 for constants and ctypes for everything else seems a little
# indecisive, but whatevs.
import pyautogui
import win32con
import sys
import ctypes
import ctypes.wintypes
import subprocess

user32 = ctypes.windll.user32
ole32 = ctypes.windll.ole32
kernel32 = ctypes.windll.kernel32

WinEventProcType = ctypes.WINFUNCTYPE(
    None,
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.HWND,
    ctypes.wintypes.LONG,
    ctypes.wintypes.LONG,
    ctypes.wintypes.DWORD,
    ctypes.wintypes.DWORD
)

# The types of events we want to listen for, and the names we'll use for
# them in the log output. Pick from
# http://msdn.microsoft.com/en-us/library/windows/desktop/dd318066(v=vs.85).aspx
eventTypes = {
    win32con.EVENT_SYSTEM_FOREGROUND: "Foreground",
    win32con.EVENT_OBJECT_FOCUS: "Focus",
    win32con.EVENT_OBJECT_SHOW: "Show",
    win32con.EVENT_SYSTEM_DIALOGSTART: "Dialog",
    win32con.EVENT_SYSTEM_CAPTURESTART: "Capture",
    win32con.EVENT_SYSTEM_MINIMIZEEND: "UnMinimize"
}


# Layout swapping code
def swapLayout(layout):
    pyautogui.hotkey(['alt', 'shift', layouts[layout]])

layouts = {
    "EN": "8",
    "NO": "9"
}
# What Process maps to what Keyboards layout
# None = No change
processLayout = {
    "ms-teams.exe": "NO",
    "explorer.exe": None,
    "msedgewebview2.exe": None,
    "ApplicationFrameHost.exe": None
}
defaultLayouts = "EN"
swapLayout(defaultLayouts)
currentLayout = defaultLayouts




# limited information would be sufficient, but our platform doesn't have it.
processFlag = getattr(win32con, 'PROCESS_QUERY_LIMITED_INFORMATION',
                      win32con.PROCESS_QUERY_INFORMATION)

threadFlag = getattr(win32con, 'THREAD_QUERY_LIMITED_INFORMATION',
                     win32con.THREAD_QUERY_INFORMATION)


# store last event time for displaying time between events
lastTime = 0

def logError(msg):
    sys.stdout.write(msg + '\n')


def getProcessID(dwEventThread, hwnd):
    # It's possible to have a window we can get a PID out of when the thread
    # isn't accessible, but it's also possible to get called with no window,
    # so we have two approaches.

    hThread = kernel32.OpenThread(threadFlag, 0, dwEventThread)

    if hThread:
        try:
            processID = kernel32.GetProcessIdOfThread(hThread)
            if not processID:
                logError("Couldn't get process for thread %s: %s" %
                         (hThread, ctypes.WinError()))
        finally:
            kernel32.CloseHandle(hThread)
    else:
        errors = ["No thread handle for %s: %s" %
                  (dwEventThread, ctypes.WinError(),)]

        if hwnd:
            processID = ctypes.wintypes.DWORD()
            threadID = user32.GetWindowThreadProcessId(
                hwnd, ctypes.byref(processID))
            if threadID != dwEventThread:
                logError("Window thread != event thread? %s != %s" %
                         (threadID, dwEventThread))
            if processID:
                processID = processID.value
            else:
                errors.append(
                    "GetWindowThreadProcessID(%s) didn't work either: %s" % (
                    hwnd, ctypes.WinError()))
                processID = None
        else:
            processID = None

        if not processID:
            for err in errors:
                logError(err)

    return processID


def getProcessFilename(processID):
    hProcess = kernel32.OpenProcess(processFlag, 0, processID)
    if not hProcess:
        logError("OpenProcess(%s) failed: %s" % (processID, ctypes.WinError()))
        return None

    try:
        filenameBufferSize = ctypes.wintypes.DWORD(4096)
        filename = ctypes.create_unicode_buffer(filenameBufferSize.value)
        kernel32.QueryFullProcessImageNameW(hProcess, 0, ctypes.byref(filename),
                                            ctypes.byref(filenameBufferSize))

        return filename.value
    finally:
        kernel32.CloseHandle(hProcess)


def callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
    global currentLayout
    length = user32.GetWindowTextLengthW(hwnd)
    title = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title, length + 1)

    processID = getProcessID(dwEventThread, hwnd)

    shortName = '?'
    newLayout = defaultLayouts
    if processID:
        filename = getProcessFilename(processID)
        if filename:
            shortName = '\\'.join(filename.rsplit('\\', 2)[-1:])
            # print(f"ShortName: {shortName}\tTitle: {title.value}")
            for key, value in processLayout.items():
                if shortName.endswith(key):
                    if(value == None):
                        return

                    newLayout = value

    if(newLayout != currentLayout):
        print(f"Switching to {newLayout} for {shortName}")
        currentLayout = newLayout
        swapLayout(newLayout)


def setHook(WinEventProc, eventType):
    return user32.SetWinEventHook(
        eventType,
        eventType,
        0,
        WinEventProc,
        0,
        0,
        win32con.WINEVENT_OUTOFCONTEXT
    )


def main():
    print("Starting up")
    ole32.CoInitialize(0)

    WinEventProc = WinEventProcType(callback)
    user32.SetWinEventHook.restype = ctypes.wintypes.HANDLE

    hookIDs = [setHook(WinEventProc, et) for et in eventTypes.keys()]
    if not any(hookIDs):
        print('SetWinEventHook failed')
        sys.exit(1)

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
        user32.TranslateMessageW(msg)
        user32.DispatchMessageW(msg)

    for hookID in hookIDs:
        user32.UnhookWinEvent(hookID)
    ole32.CoUninitialize()


if __name__ == '__main__':
    main()
