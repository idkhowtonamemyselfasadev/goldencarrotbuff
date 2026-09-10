package dev.goldencarrot;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import net.fabricmc.loader.api.FabricLoader;

import java.io.Reader;
import java.io.Writer;
import java.nio.file.Files;
import java.nio.file.Path;

/** config/goldencarrotbuff.json — written with defaults on first run. */
public final class GoldenCarrotBuffConfig {

    // --- Golden carrot --------------------------------------------------------------

    /** Let the carrot be eaten with a full hunger bar, the way a golden apple can. */
    public boolean carrot_always_edible = true;
    /** Regeneration length. 0 turns it off. */
    public double carrot_regen_seconds = 10.0;
    /** 1 = Regeneration I. */
    public int carrot_regen_level = 1;
    /** Absorption hearts handed over. Decimals are allowed; 0 turns it off. */
    public double carrot_absorption_hearts = 1.0;
    /** How long the absorption lasts before it fades, like a golden apple's 2 minutes. */
    public double carrot_absorption_seconds = 120.0;

    // --- Golden apple ---------------------------------------------------------------

    /** Leave the golden apple vanilla when false. */
    public boolean apple_enabled = true;
    /** Absorption hearts instead of vanilla's two. 0 removes the absorption entirely. */
    public double apple_absorption_hearts = 4.0;
    public double apple_absorption_seconds = 120.0;
    /** Resistance length. 0 turns it off. Vanilla Regeneration II is kept as it is. */
    public double apple_resistance_seconds = 4.0;
    /** 1 = Resistance I. */
    public int apple_resistance_level = 1;
    /** Item cooldown after finishing an apple, greyed out on the hotbar. 0 turns it off. */
    public double apple_cooldown_seconds = 3.0;

    // --- The 100 custom foods ---------------------------------------------------------

    /** Load the 100 custom foods: their recipes, loot drops, villager trades and /gcbfood. */
    public boolean custom_foods = true;

    /** Log every carrot, apple and custom food eaten to the console. */
    public boolean debug = false;

    private static final Gson GSON = new GsonBuilder().setPrettyPrinting().create();

    private static Path path() {
        return FabricLoader.getInstance().getConfigDir().resolve("goldencarrotbuff.json");
    }

    public static GoldenCarrotBuffConfig load() {
        Path path = path();
        if (Files.exists(path)) {
            try (Reader reader = Files.newBufferedReader(path)) {
                GoldenCarrotBuffConfig config = GSON.fromJson(reader, GoldenCarrotBuffConfig.class);
                if (config != null) {
                    return config;
                }
                GoldenCarrotBuff.LOGGER.warn("goldencarrotbuff.json was empty; using defaults.");
            } catch (Exception e) {
                // A broken config must never stop the server booting.
                GoldenCarrotBuff.LOGGER.error("Could not read goldencarrotbuff.json, using defaults", e);
                return new GoldenCarrotBuffConfig();
            }
        }
        GoldenCarrotBuffConfig config = new GoldenCarrotBuffConfig();
        config.save();
        return config;
    }

    public void save() {
        try {
            Path path = path();
            Files.createDirectories(path.getParent());
            try (Writer writer = Files.newBufferedWriter(path)) {
                GSON.toJson(this, writer);
            }
        } catch (Exception e) {
            GoldenCarrotBuff.LOGGER.error("Could not write goldencarrotbuff.json", e);
        }
    }
}
