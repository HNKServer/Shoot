package moe.honoka.npps4wrapper

import android.content.Context

object HeaderState {
    private const val PREF = "npps4_wrapper_ui"
    private const val KEY_HIDDEN = "love_arrow_header_hidden"

    fun isHidden(context: Context): Boolean =
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).getBoolean(KEY_HIDDEN, false)

    fun setHidden(context: Context, hidden: Boolean) {
        context.getSharedPreferences(PREF, Context.MODE_PRIVATE).edit().putBoolean(KEY_HIDDEN, hidden).apply()
    }

    fun toggle(context: Context): Boolean {
        val now = !isHidden(context)
        setHidden(context, now)
        return now
    }

    fun toggleText(context: Context): String = if (isHidden(context)) "▲" else "▼"
}
