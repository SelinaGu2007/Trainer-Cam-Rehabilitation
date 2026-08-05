#ifndef ANALYSE_H
#define ANALYSE_H

#include <QWidget>
#include <QDir>
#include <QShowEvent>
#include <QMessageBox>
#include <QProcess>
#include <QListWidgetItem>
#include <QStringList>
#include <QTimer>
namespace Ui {
class Analyse;
}

class Analyse : public QWidget
{
    Q_OBJECT

public:
    explicit Analyse(QWidget *parent = nullptr);
    ~Analyse();

    void displayListDirectories1(const QString& directory);
    void startFeedbackPolling(
        const QString &feedbackPath,
        const QString &reviewPath,
        const QString &customerFolder,
        const QString &tutorFolder);
private slots:
    void on_pushButtonAnalyse_clicked();
    void onShowEvent1();
    void on_pushButtonDelete_clicked();
    void tryShowFeedback();

private:
    Ui::Analyse *ui;
    QString TutorFolder;
    QString MyRecordingFolder;
    QString AnalyzerProgram;
    QStringList AnalyzerPrefixArguments;
    QString ExerciseProfile;
    QString SubjectTrackingConfig;
    QString FeedbackLocale;
    bool VoiceFeedbackEnabled = true;
    double VoiceRate = 0.0;
    double VoiceVolume = 0.8;
    QTimer *FeedbackTimer = nullptr;
    QString PendingFeedbackPath;
    QString PendingReviewPath;
    QString PendingCustomerFolder;
    QString PendingTutorFolder;
    int FeedbackPollAttempts = 0;

protected:
    void showEvent(QShowEvent *event) override;

};

#endif // ANALYSE_H
