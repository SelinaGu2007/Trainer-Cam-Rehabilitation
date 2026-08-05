#ifndef ASSESSMENTRESULTDIALOG_H
#define ASSESSMENTRESULTDIALOG_H

#include <QDialog>
#include <QJsonObject>

class QCheckBox;
class QPushButton;
class QTextToSpeech;

class AssessmentResultDialog : public QDialog
{
    Q_OBJECT

public:
    explicit AssessmentResultDialog(
        const QString &summaryPath,
        bool voiceEnabledByDefault,
        double voiceRate,
        double voiceVolume,
        QWidget *parent = nullptr);

    bool isValid() const;

private slots:
    void speak();
    void voiceToggled(bool enabled);

private:
    bool loadSummary(const QString &summaryPath);
    void buildInterface(bool voiceEnabledByDefault, double voiceRate, double voiceVolume);

    QJsonObject Summary;
    QString Locale;
    QString SpokenText;
    bool Valid = false;
    QTextToSpeech *Speech = nullptr;
    QCheckBox *VoiceCheckBox = nullptr;
    QPushButton *SpeakButton = nullptr;
};

#endif // ASSESSMENTRESULTDIALOG_H
