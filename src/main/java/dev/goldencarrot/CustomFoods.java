package dev.goldencarrot;

import com.google.gson.Gson;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.mojang.serialization.JsonOps;
import net.fabricmc.fabric.api.loot.v3.LootTableEvents;
import net.fabricmc.fabric.api.object.builder.v1.trade.TradeOfferHelper;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.RegistryOps;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.entity.npc.villager.VillagerProfession;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.trading.ItemCost;
import net.minecraft.world.item.trading.MerchantOffer;
import net.minecraft.world.level.storage.loot.LootPool;
import net.minecraft.world.level.storage.loot.LootTable;
import net.minecraft.world.level.storage.loot.entries.NestedLootTable;

import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The 100 custom foods, read from {@code foods.json} in the jar (written by
 * {@code foods.py}).
 *
 * <p>There is no new item anywhere: every food is a vanilla bread with components a
 * vanilla client already knows how to draw and eat. The recipes and the loot pools are
 * plain datapack JSON in the jar; this class only builds the stacks for the command and
 * the trades, and hooks the loot pools into the vanilla tables they belong in.
 */
public final class CustomFoods {

    public static final String TAG = "gcb_food";

    /** One food: its id, display name, and the {@code ItemStack} JSON that makes it. */
    public record Food(String id, String name, JsonElement stack) {}

    public record Trade(String profession, int level, String food, int count, int emeralds) {}

    private static final Gson GSON = new Gson();

    private final Map<String, Food> foods = new LinkedHashMap<>();
    private final Map<String, List<String>> lootInjections = new LinkedHashMap<>();
    private final List<Trade> trades = new ArrayList<>();

    private CustomFoods() {}

    public static CustomFoods load() {
        CustomFoods result = new CustomFoods();
        try (Reader reader = new InputStreamReader(
                CustomFoods.class.getResourceAsStream("/foods.json"), StandardCharsets.UTF_8)) {
            JsonObject root = GSON.fromJson(reader, JsonObject.class);
            for (JsonElement e : root.getAsJsonArray("foods")) {
                JsonObject o = e.getAsJsonObject();
                String id = o.get("id").getAsString();
                result.foods.put(id, new Food(id, o.get("name").getAsString(), o.get("stack")));
            }
            for (Map.Entry<String, JsonElement> entry : root.getAsJsonObject("loot_injections").entrySet()) {
                List<String> ours = new ArrayList<>();
                entry.getValue().getAsJsonArray().forEach(t -> ours.add(t.getAsString()));
                result.lootInjections.put(entry.getKey(), ours);
            }
            for (JsonElement e : root.getAsJsonArray("trades")) {
                JsonObject o = e.getAsJsonObject();
                result.trades.add(new Trade(o.get("profession").getAsString(), o.get("level").getAsInt(),
                        o.get("food").getAsString(), o.get("count").getAsInt(), o.get("emeralds").getAsInt()));
            }
        } catch (Exception e) {
            GoldenCarrotBuff.LOGGER.error("Could not read foods.json; the custom foods are off", e);
        }
        return result;
    }

    public Map<String, Food> foods() {
        return Collections.unmodifiableMap(foods);
    }

    public Map<String, List<String>> lootInjections() {
        return Collections.unmodifiableMap(lootInjections);
    }

    public List<Trade> trades() {
        return Collections.unmodifiableList(trades);
    }

    /** A fresh stack of the food, or empty if the id is unknown. */
    public ItemStack create(HolderLookup.Provider registries, String id, int count) {
        Food food = foods.get(id);
        if (food == null) {
            return ItemStack.EMPTY;
        }
        RegistryOps<JsonElement> ops = RegistryOps.create(JsonOps.INSTANCE, registries);
        ItemStack stack = ItemStack.CODEC.parse(ops, food.stack())
                .resultOrPartial(error -> GoldenCarrotBuff.LOGGER.error("Food {} does not parse: {}", id, error))
                .orElse(ItemStack.EMPTY);
        if (!stack.isEmpty()) {
            stack.setCount(count);
        }
        return stack;
    }

    /** Which custom food a stack is, or null for anything else. */
    public static String foodIdOf(ItemStack stack) {
        CustomData data = stack.get(DataComponents.CUSTOM_DATA);
        if (data == null) {
            return null;
        }
        String id = data.copyTag().getStringOr(TAG, "");
        return id.isEmpty() ? null : id;
    }

    /** Add our loot pools to the vanilla tables, and our offers to the villagers. */
    public void register() {
        LootTableEvents.MODIFY.register((key, tableBuilder, source, registries) -> {
            List<String> ours = lootInjections.get(key.identifier().toString());
            if (ours == null) {
                return;
            }
            for (String table : ours) {
                ResourceKey<LootTable> ourKey = ResourceKey.create(Registries.LOOT_TABLE, Identifier.parse(table));
                tableBuilder.withPool(LootPool.lootPool().add(NestedLootTable.lootTableReference(ourKey)));
            }
        });

        for (Trade trade : trades) {
            ResourceKey<VillagerProfession> profession = switch (trade.profession()) {
                case "farmer" -> VillagerProfession.FARMER;
                case "butcher" -> VillagerProfession.BUTCHER;
                case "fisherman" -> VillagerProfession.FISHERMAN;
                case "shepherd" -> VillagerProfession.SHEPHERD;
                case "cleric" -> VillagerProfession.CLERIC;
                default -> null;
            };
            if (profession == null) {
                GoldenCarrotBuff.LOGGER.warn("Unknown villager profession {} for {}", trade.profession(), trade.food());
                continue;
            }
            TradeOfferHelper.registerVillagerOffers(profession, trade.level(), factories ->
                    factories.add((level, entity, random) -> {
                        ItemStack stack = create(level.registryAccess(), trade.food(), trade.count());
                        if (stack.isEmpty()) {
                            return null;
                        }
                        // 12 uses, 5 xp, the usual 5% price bump.
                        return new MerchantOffer(new ItemCost(Items.EMERALD, trade.emeralds()), stack, 12, 5, 0.05F);
                    }));
        }
    }
}
