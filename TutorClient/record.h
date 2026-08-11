#ifndef RECORD_H
#define RECORD_H

#include <QWidget>
#include <QDir>
#include <QPointer>
#include <QProcess>
#include <QShowEvent>
#include <QListWidgetItem>
#include <QMessageBox>
#include <QInputDialog>
#include <QFileDialog>
namespace Ui {
class Record;
}

class Record : public QWidget
{
    Q_OBJECT

public:
    explicit Record(QWidget *parent = nullptr);
    ~Record();

    void displayListDirectories(const QString& directory);
private slots:
    void on_pushButtonRecord_clicked();
    void onShowEvent();

    void on_pushButtonDispaly_clicked();


    void on_pushButtonDelete_clicked();

private:
    QString safeSessionPath(const QString &sessionName) const;
    void setRecordingUi(bool recording);
    void finishRecorderProcess(QProcess *process);
    void offerIncompleteRecordingCleanup(const QString &directoryPath);

    Ui::Record *ui;
    QPointer<QProcess> RecorderProcess;
    QString RecordButtonText;
    QString TutorFolder;
    QString RecorderProgram;
    QString VideoPlayerProgram;

protected:
    void showEvent(QShowEvent *event) override;
};

#endif // RECORD_H
