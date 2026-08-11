#include "processwindowtracker.h"

#include <QElapsedTimer>
#include <QPointer>
#include <QProcess>
#include <QTimer>
#include <Windows.h>

#include <memory>

namespace {

struct WindowSearchContext
{
    DWORD processId;
    HWND window = nullptr;
};

BOOL CALLBACK findVisibleProcessWindowCallback(HWND window, LPARAM parameter)
{
    auto *context = reinterpret_cast<WindowSearchContext *>(parameter);
    DWORD ownerProcessId = 0;
    GetWindowThreadProcessId(window, &ownerProcessId);
    if (ownerProcessId == context->processId
        && IsWindowVisible(window)
        && GetWindow(window, GW_OWNER) == nullptr) {
        context->window = window;
        return FALSE;
    }
    return TRUE;
}

HWND findVisibleProcessWindow(qint64 processId)
{
    if (processId <= 0) {
        return nullptr;
    }
    WindowSearchContext context{static_cast<DWORD>(processId), nullptr};
    EnumWindows(findVisibleProcessWindowCallback, reinterpret_cast<LPARAM>(&context));
    return context.window;
}

void placeWindow(HWND window, ProcessWindowPlacement placement)
{
    const int screenWidth = GetSystemMetrics(SM_CXSCREEN);
    const int screenHeight = GetSystemMetrics(SM_CYSCREEN);
    if (placement == ProcessWindowPlacement::LowerThreeQuarters) {
        MoveWindow(
            window,
            0,
            screenHeight / 4,
            screenWidth,
            screenHeight * 3 / 4,
            TRUE);
        return;
    }
    MoveWindow(window, 0, 0, screenWidth, screenHeight, TRUE);
}

} // namespace

void trackProcessWindow(
    QObject *context,
    QProcess *process,
    int timeoutMs,
    ProcessWindowPlacement placement)
{
    auto *timer = new QTimer(context);
    auto elapsed = std::make_shared<QElapsedTimer>();
    QPointer<QProcess> processGuard(process);
    elapsed->start();

    QObject::connect(timer, &QTimer::timeout, context,
                     [timer, elapsed, processGuard, timeoutMs, placement]() {
        if (!processGuard) {
            timer->stop();
            timer->deleteLater();
            return;
        }
        if (HWND window = findVisibleProcessWindow(processGuard->processId())) {
            placeWindow(window, placement);
            timer->stop();
            timer->deleteLater();
            return;
        }
        if (elapsed->elapsed() >= timeoutMs
            || processGuard->state() == QProcess::NotRunning) {
            timer->stop();
            timer->deleteLater();
        }
    });
    timer->start(100);
}
