package dev.goldencarrot.mixin;

import dev.goldencarrot.CustomFoods;
import dev.goldencarrot.GoldenCarrotBuff;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.Consumable;
import net.minecraft.world.level.Level;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Hooks the moment a food is finished. Every edible item goes through
 * {@code Consumable.onConsume}, so this catches the carrot and the apple however they
 * were eaten. It runs at HEAD, while the stack is still whole and before vanilla shrinks
 * it or applies its own effects.
 */
@Mixin(Consumable.class)
public abstract class ConsumableMixin {

    @Inject(method = "onConsume", at = @At("HEAD"))
    private void goldencarrot$onEaten(Level level, LivingEntity entity, ItemStack stack,
                                      CallbackInfoReturnable<ItemStack> cir) {
        if (level.isClientSide()) {
            return;
        }
        if (stack.is(Items.GOLDEN_CARROT)) {
            GoldenCarrotBuff.onGoldenCarrotEaten(entity);
        } else if (stack.is(Items.GOLDEN_APPLE)) {
            GoldenCarrotBuff.onGoldenAppleEaten(entity, stack);
        } else {
            String food = CustomFoods.foodIdOf(stack);
            if (food != null) {
                GoldenCarrotBuff.onCustomFoodEaten(entity, food);
            }
        }
    }
}
