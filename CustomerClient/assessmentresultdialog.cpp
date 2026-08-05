#include "assessmentresultdialog.h"

#include <QCheckBox>
#include <QDialogButtonBox>
#include <QFile>
#include <QFont>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLabel>
#include <QLocale>
#include <QPushButton>
#include <QSettings>
#include <QTextToSpeech>
#include <QTimer>
#include <QVBoxLayout>

AssessmentResultDialog::AssessmentResultDialog(
    const QString &summaryPath,
    bool voiceEnabledByDefault,
    double voiceRate,
    double voiceVolume,
    QWidget *parent)
    : QDialog(parent)
{
    Valid = loadSummary(summaryPath);
    if (Valid) {
        buildInterface(voiceEnabledByDefault, voiceRate, voiceVolume);
    }
}

bool AssessmentResultDialog::isValid() const
{
    return Valid;
}

bool AssessmentResultDialog::loadSummary(const QString &summaryPath)
{
    QFile file(summaryPath);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        return false;
    }
    QJsonParseError error;
    const QJsonDocument document = QJsonDocument::fromJson(file.readAll(), &error);
    if (error.error != QJsonParseError::NoError || !document.isObject()) {
        return false;
    }
    Summary = document.object();
    if (Summary.value("format").toString() != "trainercam.feedback-summary"
        || Summary.value("schema_version").toInt() != 1) {
        return false;
    }
    Locale = Summary.value("locale").toString("en-US");
    SpokenText = Summary.value("spoken_text").toString().trimmed();
    return !SpokenText.isEmpty();
}

void AssessmentResultDialog::buildInterface(
    bool voiceEnabledByDefault, double voiceRate, double voiceVolume)
{
    const bool chinese = Locale == "zh-CN";
    setWindowTitle(chinese ? QStringLiteral("训练结果") : QStringLiteral("Session Result"));
    setMinimumSize(560, 520);
    setModal(false);

    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(28, 24, 28, 24);
    layout->setSpacing(14);

    auto *title = new QLabel(chinese ? QStringLiteral("本次训练结果") : QStringLiteral("Your session result"), this);
    QFont titleFont = title->font();
    titleFont.setPointSize(18);
    titleFont.setBold(true);
    title->setFont(titleFont);
    layout->addWidget(title);

    const double score = Summary.value("overall_score").toDouble();
    auto *scoreLabel = new QLabel(QString::number(score, 'f', score == static_cast<int>(score) ? 0 : 1) + " / 100", this);
    QFont scoreFont = scoreLabel->font();
    scoreFont.setPointSize(34);
    scoreFont.setBold(true);
    scoreLabel->setFont(scoreFont);
    const QString scoreColour = score >= 75.0 ? "#237a3b" : (score >= 60.0 ? "#a46400" : "#a12622");
    scoreLabel->setStyleSheet("color: " + scoreColour + ";");
    layout->addWidget(scoreLabel);

    const QString headline = Summary.value("rating").toObject().value("headline").toString();
    auto *headlineLabel = new QLabel(headline, this);
    QFont headlineFont = headlineLabel->font();
    headlineFont.setPointSize(15);
    headlineFont.setBold(true);
    headlineLabel->setFont(headlineFont);
    headlineLabel->setWordWrap(true);
    layout->addWidget(headlineLabel);

    auto *focusTitle = new QLabel(chinese ? QStringLiteral("重点改进") : QStringLiteral("Focus for next time"), this);
    QFont focusFont = focusTitle->font();
    focusFont.setPointSize(13);
    focusFont.setBold(true);
    focusTitle->setFont(focusFont);
    layout->addWidget(focusTitle);

    const QJsonArray improvements = Summary.value("improvements").toArray();
    if (improvements.isEmpty()) {
        auto *none = new QLabel(
            chinese ? QStringLiteral("没有持续性问题超过当前提示阈值。")
                    : QStringLiteral("No persistent issue crossed the configured feedback threshold."),
            this);
        none->setWordWrap(true);
        layout->addWidget(none);
    } else {
        for (const QJsonValue &value : improvements) {
            const QJsonObject improvement = value.toObject();
            const QString label = improvement.value("label").toString();
            const QString message = improvement.value("message").toString();
            auto *item = new QLabel(QStringLiteral("• %1\n  %2").arg(label, message), this);
            item->setWordWrap(true);
            item->setStyleSheet("font-size: 12pt;");
            layout->addWidget(item);
        }
    }

    const QString qualityNotice = Summary.value("quality_notice").toString().trimmed();
    if (!qualityNotice.isEmpty()) {
        auto *quality = new QLabel(qualityNotice, this);
        quality->setWordWrap(true);
        quality->setStyleSheet("background: #fff3cd; color: #664d03; padding: 10px; border-radius: 4px;");
        layout->addWidget(quality);
    }

    auto *disclaimer = new QLabel(Summary.value("disclaimer").toString(), this);
    disclaimer->setWordWrap(true);
    disclaimer->setStyleSheet("color: #555; font-size: 10pt;");
    layout->addWidget(disclaimer);

    Speech = new QTextToSpeech(this);
    Speech->setLocale(QLocale(Locale));
    Speech->setRate(voiceRate);
    Speech->setVolume(voiceVolume);

    QSettings settings("TrainerCam", "CustomerClient");
    const bool voiceEnabled = settings.value("feedback/voiceEnabled", voiceEnabledByDefault).toBool();
    VoiceCheckBox = new QCheckBox(
        chinese ? QStringLiteral("自动朗读训练反馈") : QStringLiteral("Read feedback aloud"), this);
    VoiceCheckBox->setChecked(voiceEnabled);
    connect(VoiceCheckBox, &QCheckBox::toggled, this, &AssessmentResultDialog::voiceToggled);
    layout->addWidget(VoiceCheckBox);

    SpeakButton = new QPushButton(chinese ? QStringLiteral("重新朗读") : QStringLiteral("Play voice feedback"), this);
    connect(SpeakButton, &QPushButton::clicked, this, &AssessmentResultDialog::speak);
    layout->addWidget(SpeakButton);

    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Close, this);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::close);
    layout->addWidget(buttons);

    if (voiceEnabled) {
        QTimer::singleShot(250, this, &AssessmentResultDialog::speak);
    }
}

void AssessmentResultDialog::speak()
{
    if (Speech && !SpokenText.isEmpty()) {
        Speech->stop();
        Speech->say(SpokenText);
    }
}

void AssessmentResultDialog::voiceToggled(bool enabled)
{
    QSettings settings("TrainerCam", "CustomerClient");
    settings.setValue("feedback/voiceEnabled", enabled);
    SpeakButton->setEnabled(enabled);
    if (!enabled && Speech) {
        Speech->stop();
    } else if (enabled) {
        speak();
    }
}
