#ifndef PROCESSWINDOWTRACKER_H
#define PROCESSWINDOWTRACKER_H

class QObject;
class QProcess;

enum class ProcessWindowPlacement
{
    PrimaryScreen,
    LowerThreeQuarters
};

void trackProcessWindow(
    QObject *context,
    QProcess *process,
    int timeoutMs,
    ProcessWindowPlacement placement);

#endif // PROCESSWINDOWTRACKER_H
