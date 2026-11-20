// What the app shows first. It gets the game ready and starts it:
//
// 1. Unpacks the game's files from the app (assets/game: dsp_coef.bin, wii_bootstrap, ...) to
//    Game/ in the app's folder, once per version of the app.
// 2. Writes portable.txt (settings, saves and logs go to UserData/) and, the first time,
//    UserData/Config.toml with the disc's folder.
// 3. Checks that the disc is there (Disc/DATA/sys/main.dol). If it is not, it says where to copy
//    it and waits; otherwise it starts the game (GameActivity).
//
// The app's folder is the one Android gives every app on the shared storage:
//   Android/data/io.github.hmaprecomp.animalparade/files
// A computer sees it over USB, and the build script copies the disc there with adb.
//
// Lo primero que muestra la app: desempaca los archivos del juego, escribe la configuración la
// primera vez, revisa que el disco esté en la carpeta de la app y arranca el juego. Si falta el
// disco, dice dónde copiarlo.

package io.github.hmaprecomp.animalparade;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.res.AssetManager;
import android.graphics.Color;
import android.os.Bundle;
import android.util.TypedValue;
import android.view.Gravity;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

public class SetupActivity extends Activity {
    static final String GAME_FOLDER = "Game";
    private static final String ASSET_ROOT = "game";
    private static final String VERSION_FILE = "app-version.txt";

    private TextView mText;
    private Button mRetry;

    // The app's own folder on the shared storage, or null while that storage is not available.
    static File dataRoot(Context context) {
        return context.getExternalFilesDir(null);
    }

    private static boolean spanish() {
        return "es".equals(Locale.getDefault().getLanguage());
    }

    private static String say(String english, String spanish) {
        return spanish() ? spanish : english;
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        int padding = (int) TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 24, getResources().getDisplayMetrics());
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(padding, padding, padding, padding);
        layout.setBackgroundColor(Color.rgb(32, 40, 24));
        mText = new TextView(this);
        mText.setTextColor(Color.WHITE);
        mText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17);
        mText.setTextIsSelectable(true);
        mRetry = new Button(this);
        mRetry.setText(say("Try again", "Reintentar"));
        mRetry.setVisibility(Button.GONE);
        mRetry.setOnClickListener(new android.view.View.OnClickListener() {
            @Override
            public void onClick(android.view.View view) {
                prepare();
            }
        });
        layout.addView(mText);
        layout.addView(mRetry);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(layout);
        setContentView(scroll);
        prepare();
    }

    private void prepare() {
        mRetry.setVisibility(Button.GONE);
        mText.setGravity(Gravity.CENTER);
        mText.setText(say("Getting the game ready…", "Preparando el juego…"));
        final SetupActivity activity = this;
        new Thread(new Runnable() {
            @Override
            public void run() {
                final File root = dataRoot(activity);
                String problem = null;
                if (root == null) {
                    problem = say("The shared storage is not available right now.",
                                  "El almacenamiento compartido no está disponible ahora.");
                } else {
                    try {
                        unpackGameFiles(root);
                        writeFirstSettings(root);
                    } catch (IOException e) {
                        problem = say("The game's files could not be unpacked: ", "No se pudieron desempacar los archivos del juego: ")
                                + e.getMessage();
                    }
                }
                final String error = problem;
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        if (error != null) {
                            showProblem(error);
                        } else if (!discFile(root).isFile()) {
                            showDiscHelp(root);
                        } else {
                            startActivity(new Intent(activity, GameActivity.class));
                            finish();
                        }
                    }
                });
            }
        }).start();
    }

    private static File discFile(File root) {
        return new File(root, "Disc/DATA/sys/main.dol");
    }

    private void showProblem(String text) {
        mText.setGravity(Gravity.START);
        mText.setText(text);
        mRetry.setVisibility(Button.VISIBLE);
    }

    private void showDiscHelp(File root) {
        String folder = new File(root, "Disc/DATA").getAbsolutePath();
        showProblem(say(
            "The game needs your disc's files.\n\n"
            + "Copy the DATA folder that the computer version made (Disc/DATA, with sys/ and files/ in it) to:\n\n"
            + folder + "\n\n"
            + "build-android on your computer does this for you when the device is connected with USB debugging. "
            + "Or copy it over USB: the folder is Android/data/" + getPackageName() + "/files on the device.",
            "El juego necesita los archivos de tu disco.\n\n"
            + "Copia la carpeta DATA que hizo la versión de computadora (Disc/DATA, con sys/ y files/ dentro) a:\n\n"
            + folder + "\n\n"
            + "build-android en tu computadora lo hace por ti cuando el dispositivo está conectado con la depuración USB. "
            + "O cópiala por USB: la carpeta es Android/data/" + getPackageName() + "/files en el dispositivo."));
    }

    // assets/game -> Game/, when the app's version differs from the one unpacked there.
    private void unpackGameFiles(File root) throws IOException {
        File game = new File(root, GAME_FOLDER);
        // The version, and when this copy of the app was installed: a rebuilt app of the same
        // version still unpacks its files again.
        long code = 0;
        try {
            code = getPackageManager().getPackageInfo(getPackageName(), 0).getLongVersionCode();
        } catch (android.content.pm.PackageManager.NameNotFoundException e) {
            // Not possible for the app itself.
        }
        String version = code + " " + new File(getApplicationInfo().sourceDir).lastModified();
        File stamp = new File(game, VERSION_FILE);
        if (stamp.isFile() && version.equals(readText(stamp))) {
            return;
        }
        deleteTree(game);
        copyAssets(getAssets(), ASSET_ROOT, game);
        writeText(stamp, version);
    }

    private static void copyAssets(AssetManager assets, String path, File to) throws IOException {
        String[] children = assets.list(path);
        if (children != null && children.length > 0) {
            if (!to.isDirectory() && !to.mkdirs()) {
                throw new IOException("cannot make " + to);
            }
            for (String child : children) {
                copyAssets(assets, path + "/" + child, new File(to, child));
            }
            return;
        }
        try (InputStream in = assets.open(path); OutputStream out = new FileOutputStream(to)) {
            byte[] buffer = new byte[1 << 16];
            int read;
            while ((read = in.read(buffer)) > 0) {
                out.write(buffer, 0, read);
            }
        }
    }

    // portable.txt, and Config.toml with the disc's folder the first time.
    private static void writeFirstSettings(File root) throws IOException {
        File portable = new File(root, "portable.txt");
        if (!portable.isFile()) {
            writeText(portable, "Harvest Moon: Animal Parade keeps its user data in UserData.\n");
        }
        File config = new File(root, "UserData/Config.toml");
        if (!config.isFile()) {
            String disc = new File(root, "Disc/DATA").getAbsolutePath().replace("\\", "\\\\").replace("\"", "\\\"");
            writeText(config, "[paths]\ndvd_root = \"" + disc + "\"\n");
        }
    }

    private static String readText(File file) throws IOException {
        try (InputStream in = new java.io.FileInputStream(file)) {
            byte[] bytes = new byte[(int) file.length()];
            int at = 0;
            while (at < bytes.length) {
                int read = in.read(bytes, at, bytes.length - at);
                if (read < 0) break;
                at += read;
            }
            return new String(bytes, 0, at, StandardCharsets.UTF_8);
        }
    }

    private static void writeText(File file, String text) throws IOException {
        File parent = file.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
            throw new IOException("cannot make " + parent);
        }
        try (OutputStream out = new FileOutputStream(file)) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
        }
    }

    private static void deleteTree(File file) {
        File[] children = file.listFiles();
        if (children != null) {
            for (File child : children) {
                deleteTree(child);
            }
        }
        file.delete();
    }
}
