// The game: SDL's activity, with two changes.
//
// - SDL is compiled into the game (libmain.so), so that is the one library to load.
// - The drawing surface is aurora's, which tells the renderer when the surface can be drawn on
//   (the game waits while the app is in the background).
//
// Before SDL starts the game it is told where the game's files are (SetupActivity unpacked them):
// WIICOMPILED_GAME_DIR, which the runtime uses as the folder its program is in. portable.txt
// beside that folder keeps the settings, saves and logs in UserData there.
//
// El juego: la actividad de SDL. SDL va dentro de libmain.so, la superficie de dibujo es la de
// aurora, y antes de empezar se le dice al runtime dónde están los archivos del juego.

package io.github.hmaprecomp.animalparade;

import android.content.Context;
import android.os.Bundle;
import android.system.ErrnoException;
import android.system.Os;
import android.util.Log;

import dev.encounter.aurora.AuroraSurface;

import org.libsdl.app.SDLActivity;
import org.libsdl.app.SDLSurface;

import java.io.File;

public class GameActivity extends SDLActivity {
    private static final String TAG = "AnimalParade";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        File root = SetupActivity.dataRoot(this);
        if (root != null) {
            try {
                Os.setenv("WIICOMPILED_GAME_DIR", new File(root, SetupActivity.GAME_FOLDER).getAbsolutePath(), true);
                Os.setenv("HOME", root.getAbsolutePath(), true);
            } catch (ErrnoException e) {
                Log.e(TAG, "Could not name the game's folder", e);
            }
        }
        super.onCreate(savedInstanceState);
    }

    @Override
    protected String[] getLibraries() {
        return new String[] { "main" };
    }

    @Override
    protected SDLSurface createSDLSurface(Context context) {
        return new AuroraSurface(context);
    }
}
