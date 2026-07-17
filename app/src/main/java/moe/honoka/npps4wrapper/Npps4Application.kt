package moe.honoka.npps4wrapper

import android.app.Application

class Npps4Application : Application() {
    override fun onCreate() {
        super.onCreate()
        CrashReporter.install(this)

        // Preload the NDK C++ shared runtime for native Python wheels.
        // greenlet is loaded from Chaquopy's requirements directory rather than
        // the normal app lib directory, so explicitly loading c++_shared here
        // makes its dependency visible before SQLAlchemy imports greenlet.
        try {
            System.loadLibrary("c++_shared")
        } catch (t: Throwable) {
            CrashReporter.append(this, "load c++_shared failed; native greenlet may fail", t)
        }
    }
}
