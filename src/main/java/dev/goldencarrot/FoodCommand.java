package dev.goldencarrot;

import com.mojang.brigadier.arguments.IntegerArgumentType;
import com.mojang.brigadier.arguments.StringArgumentType;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.commands.SharedSuggestionProvider;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.core.HolderGetter;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.registries.Registries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.permissions.Permission;
import net.minecraft.server.permissions.PermissionLevel;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.crafting.Recipe;
import net.minecraft.world.level.storage.loot.LootTable;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * {@code /gcbfood give <players> <food> [count]}, {@code /gcbfood list} and
 * {@code /gcbfood verify}, for operators (level 2, the same as /give).
 */
public final class FoodCommand {

    private static final Permission GAMEMASTER = new Permission.HasCommandLevel(PermissionLevel.GAMEMASTERS);

    private FoodCommand() {}

    public static void register(CustomFoods foods) {
        CommandRegistrationCallback.EVENT.register((dispatcher, registries, environment) ->
                dispatcher.register(Commands.literal("gcbfood")
                        .requires(source -> source.permissions().hasPermission(GAMEMASTER))
                        .then(Commands.literal("list").executes(ctx -> list(ctx.getSource(), foods)))
                        .then(Commands.literal("verify").executes(ctx -> verify(ctx.getSource(), foods)))
                        .then(Commands.literal("give")
                                .then(Commands.argument("targets", EntityArgument.players())
                                        .then(Commands.argument("food", StringArgumentType.word())
                                                .suggests((ctx, builder) ->
                                                        SharedSuggestionProvider.suggest(foods.foods().keySet(), builder))
                                                .executes(ctx -> give(ctx, foods, 1))
                                                .then(Commands.argument("count", IntegerArgumentType.integer(1, 64))
                                                        .executes(ctx -> give(ctx, foods,
                                                                IntegerArgumentType.getInteger(ctx, "count")))))))));
    }

    private static int list(CommandSourceStack source, CustomFoods foods) {
        String names = String.join(", ", foods.foods().keySet());
        source.sendSuccess(() -> Component.literal(foods.foods().size() + " foods: " + names), false);
        return foods.foods().size();
    }

    private static int give(CommandContext<CommandSourceStack> ctx, CustomFoods foods, int count)
            throws CommandSyntaxException {
        String id = StringArgumentType.getString(ctx, "food");
        CommandSourceStack source = ctx.getSource();
        ItemStack stack = foods.create(source.registryAccess(), id, count);
        if (stack.isEmpty()) {
            source.sendFailure(Component.literal("Unknown food: " + id));
            return 0;
        }
        int given = 0;
        for (ServerPlayer player : EntityArgument.getPlayers(ctx, "targets")) {
            player.getInventory().placeItemBackInInventory(stack.copy());
            given++;
        }
        int total = given;
        source.sendSuccess(() -> Component.literal("Gave " + count + " " + stack.getHoverName().getString()
                + " to " + total + " player(s)"), true);
        return given;
    }

    /** Every food parses, has a recipe, and every loot table on both sides exists. */
    private static int verify(CommandSourceStack source, CustomFoods foods) {
        MinecraftServer server = source.getServer();
        List<String> problems = new ArrayList<>();
        int recipes = 0;
        for (CustomFoods.Food food : foods.foods().values()) {
            ItemStack stack = foods.create(source.registryAccess(), food.id(), 1);
            if (stack.isEmpty()) {
                problems.add(food.id() + ": stack does not parse");
                continue;
            }
            if (!food.id().equals(CustomFoods.foodIdOf(stack))) {
                problems.add(food.id() + ": custom_data tag missing");
            }
            if (!stack.has(DataComponents.FOOD) || !stack.has(DataComponents.CONSUMABLE)) {
                problems.add(food.id() + ": not edible");
            }
            ResourceKey<Recipe<?>> recipe = ResourceKey.create(Registries.RECIPE,
                    Identifier.fromNamespaceAndPath(GoldenCarrotBuff.MOD_ID, food.id()));
            if (server.getRecipeManager().byKey(recipe).isEmpty()) {
                problems.add(food.id() + ": recipe " + recipe.identifier() + " not loaded");
            } else {
                recipes++;
            }
        }
        HolderGetter<LootTable> tables = server.reloadableRegistries().lookup().lookupOrThrow(Registries.LOOT_TABLE);
        int injected = 0;
        for (Map.Entry<String, List<String>> entry : foods.lootInjections().entrySet()) {
            ResourceKey<LootTable> vanilla = ResourceKey.create(Registries.LOOT_TABLE, Identifier.parse(entry.getKey()));
            if (tables.get(vanilla).isEmpty()) {
                problems.add("vanilla loot table " + entry.getKey() + " does not exist");
                continue;
            }
            for (String ours : entry.getValue()) {
                ResourceKey<LootTable> key = ResourceKey.create(Registries.LOOT_TABLE, Identifier.parse(ours));
                if (tables.get(key).isEmpty()) {
                    problems.add("our loot table " + ours + " did not load");
                } else {
                    injected++;
                }
            }
        }
        String summary = "verify: " + foods.foods().size() + " foods, " + recipes + " recipes, " + injected
                + " loot injections, " + problems.size() + " problems";
        for (String problem : problems) {
            GoldenCarrotBuff.LOGGER.warn("verify: {}", problem);
        }
        GoldenCarrotBuff.LOGGER.info(summary);
        source.sendSuccess(() -> Component.literal(summary), false);
        return problems.isEmpty() ? 1 : 0;
    }
}
