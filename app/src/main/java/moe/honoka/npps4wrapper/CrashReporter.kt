package moe.honoka.npps4wrapper

import android.content.Context
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object CrashReporter {
    private const val FILE_NAME = "npps4-wrapper-crash.log"

    fun install(context: Context) {
        val appContext = context.applicationContext
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            try {
                append(appContext, "UNCAUGHT on ${thread.name}", throwable)
            } catch (_: Throwable) {
                // Ignore logging failures so the original crash path is preserved.
            }
            previous?.uncaughtException(thread, throwable)
        }
    }

    fun file(context: Context): File = File(context.getExternalFilesDir(null), FILE_NAME)

    fun read(context: Context, maxChars: Int = 12000): String {
        val f = file(context)
        if (!f.exists()) return ""
        val text = f.readText(Charsets.UTF_8)
        return if (text.length <= maxChars) text else text.takeLast(maxChars)
    }

    fun clear(context: Context) {
        file(context).delete()
    }

    fun append(context: Context, title: String, throwable: Throwable? = null, message: String? = null) {
        val ts = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US).format(Date())
        val body = buildString {
            append("\n==== ").append(ts).append(" ").append(title).append(" ====\n")
            if (!message.isNullOrBlank()) append(message).append('\n')
            if (throwable != null) append(throwable.stackTraceToString()).append('\n')
        }
        val f = file(context)
        f.parentFile?.mkdirs()
        f.appendText(body, Charsets.UTF_8)
    }
}
