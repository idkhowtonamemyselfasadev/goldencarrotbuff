package dev.goldencarrot;

import net.fabricmc.api.DedicatedServerModInitializer;
import net.fabricmc.fabric.api.item.v1.DefaultItemComponentEvents;
import net.minecraft.core.component.DataComponents;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.food.FoodProperties;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.Consumable;
import net.minecraft.world.item.consume_effects.ApplyStatusEffectsConsumeEffect;
import net.minecraft.world.item.consume_effects.ConsumeEffect;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;

/**
 * GoldenCarrotBuff — golden carrots are edible at full hunger and give a short
 * regeneration plus one absorption heart; golden apples give four absorption hearts,
 * a burst of resistance, and go on a short cooldown.
 *
 * <p>Server-side only. The item components are rewritten on the server at boot; a
 * vanilla client still sends the use packet before it decides for itself whether it can
 * eat, and then follows the server's "eating" flag for the animation, so nobody installs
 * anything. The cooldown is the vanilla one the server already tells the client about.
 *
 * <p>The buffs themselves are applied from {@code ConsumableMixin} at the moment the
 * food is finished.
 */
public final class GoldenCarrotBuff implements DedicatedServerModInitializer {

    public static final Logger LOGGER = LoggerFactory.getLogger("GoldenCarrotBuff");
    public static final String MOD_ID = "goldencarrotbuff";

    private static GoldenCarrotBuffConfig config = new GoldenCarrotBuffConfig();
    private static CustomFoods foods = null;

    public static CustomFoods foods() {
        return foods;
    }

    @Override
    public void onInitializeServer() {
        config = GoldenCarrotBuffConfig.load();

        if (config.custom_foods) {
            foods = CustomFoods.load();
            foods.register();
            FoodCommand.register(foods);
            LOGGER.info("{} custom foods loaded, dropped into {} loot tables, {} villager trades",
                    foods.foods().size(), foods.lootInjections().size(), foods.trades().size());
        }

        // Fires once, when the item registry freezes, after every mod has registered.
        DefaultItemComponentEvents.MODIFY.register(context -> {
            if (config.carrot_always_edible) {
                context.modify(Items.GOLDEN_CARROT, builder -> {
                    FoodProperties food = Items.GOLDEN_CARROT.components().get(DataComponents.FOOD);
                    // Vanilla golden carrot: 6 nutrition, 14.4 saturation. Only the flag changes.
                    int nutrition = food == null ? 6 : food.nutrition();
                    float saturation = food == null ? 14.4F : food.saturation();
                    builder.set(DataComponents.FOOD, new FoodProperties(nutrition, saturation, true));
                });
            }
            if (config.apple_enabled) {
                // Vanilla's Absorption I is stripped from the apple so the config owns the
                // number of hearts; Regeneration II and everything else stays.
                context.modify(Items.GOLDEN_APPLE, builder -> {
                    Consumable old = Items.GOLDEN_APPLE.components().get(DataComponents.CONSUMABLE);
                    if (old == null) {
                        return;
                    }
                    List<ConsumeEffect> kept = new ArrayList<>();
                    for (ConsumeEffect effect : old.onConsumeEffects()) {
                        if (effect instanceof ApplyStatusEffectsConsumeEffect apply) {
                            List<MobEffectInstance> rest = apply.effects().stream()
                                    .filter(instance -> !instance.is(MobEffects.ABSORPTION))
                                    .toList();
                            if (!rest.isEmpty()) {
                                kept.add(new ApplyStatusEffectsConsumeEffect(rest, apply.probability()));
                            }
                        } else {
                            kept.add(effect);
                        }
                    }
                    builder.set(DataComponents.CONSUMABLE, new Consumable(old.consumeSeconds(),
                            old.animation(), old.sound(), old.hasConsumeParticles(), kept));
                });
            }
        });

        LOGGER.info("Golden carrot: {}Regeneration {} for {}s, {} absorption heart(s) for {}s",
                config.carrot_always_edible ? "edible at full hunger, " : "",
                config.carrot_regen_level, config.carrot_regen_seconds,
                config.carrot_absorption_hearts, config.carrot_absorption_seconds);
        if (config.apple_enabled) {
            LOGGER.info("Golden apple: {} absorption heart(s) for {}s, Resistance {} for {}s, {}s cooldown",
                    config.apple_absorption_hearts, config.apple_absorption_seconds,
                    config.apple_resistance_level, config.apple_resistance_seconds,
                    config.apple_cooldown_seconds);
        }
    }

    /** Called by the mixin on the server whenever one of the custom foods is finished. */
    public static void onCustomFoodEaten(LivingEntity entity, String foodId) {
        if (config.debug) {
            LOGGER.info("{} ate {}", entity.getName().getString(), foodId);
        }
    }

    /** Called by the mixin on the server, once per carrot finished. */
    public static void onGoldenCarrotEaten(LivingEntity entity) {
        float before = entity.getAbsorptionAmount();
        addEffect(entity, MobEffects.REGENERATION, config.carrot_regen_seconds, config.carrot_regen_level);
        grantAbsorption(entity, config.carrot_absorption_hearts, config.carrot_absorption_seconds);
        if (config.debug) {
            LOGGER.info("{} ate a golden carrot: absorption {} -> {}", entity.getName().getString(),
                    before, entity.getAbsorptionAmount());
        }
    }

    /** Called by the mixin on the server, once per apple finished, with the stack still whole. */
    public static void onGoldenAppleEaten(LivingEntity entity, ItemStack stack) {
        if (!config.apple_enabled) {
            return;
        }
        float before = entity.getAbsorptionAmount();
        addEffect(entity, MobEffects.RESISTANCE, config.apple_resistance_seconds, config.apple_resistance_level);
        grantAbsorption(entity, config.apple_absorption_hearts, config.apple_absorption_seconds);
        int cooldown = ticks(config.apple_cooldown_seconds);
        if (cooldown > 0 && entity instanceof Player player) {
            // The vanilla item cooldown: the server refuses the use and the client greys
            // the apple out on its own.
            player.getCooldowns().addCooldown(stack, cooldown);
        }
        if (config.debug) {
            LOGGER.info("{} ate a golden apple: absorption {} -> {}", entity.getName().getString(),
                    before, entity.getAbsorptionAmount());
        }
    }

    private static int ticks(double seconds) {
        return (int) Math.round(seconds * 20.0);
    }

    private static void addEffect(LivingEntity entity, net.minecraft.core.Holder<net.minecraft.world.effect.MobEffect> effect,
                                  double seconds, int level) {
        int duration = ticks(seconds);
        if (duration > 0 && level > 0) {
            // Amplifier 0 is level I.
            entity.addEffect(new MobEffectInstance(effect, duration, level - 1));
        }
    }

    /**
     * Hands over exactly {@code hearts} of absorption, through the real Absorption effect so
     * the player gets the icon, the timer, and vanilla persistence across relogs. Each level of
     * the effect raises the ceiling by two hearts and starts the player at that ceiling, so the
     * smallest level that fits is used and the amount is written back down right after.
     * Only ever upward: eating again tops you back up but never stacks, and a bigger shield
     * granted elsewhere is left alone.
     */
    private static void grantAbsorption(LivingEntity entity, double hearts, double seconds) {
        float shield = (float) (hearts * 2.0);
        int duration = ticks(seconds);
        if (shield <= 0.0F || duration <= 0) {
            return;
        }
        int amplifier = Math.max(0, (int) Math.ceil(shield / 4.0) - 1);
        float before = entity.getAbsorptionAmount();
        entity.addEffect(new MobEffectInstance(MobEffects.ABSORPTION, duration, amplifier));
        entity.setAbsorptionAmount(Math.max(before, shield));
    }
}
