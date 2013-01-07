package org.jetbrains.jps.builders.java;

import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;
import org.jetbrains.jps.builders.BuildTargetLoader;
import org.jetbrains.jps.builders.BuildTargetType;
import org.jetbrains.jps.incremental.ModuleBuildTarget;
import org.jetbrains.jps.model.JpsModel;
import org.jetbrains.jps.model.module.JpsModule;

import java.util.*;

/**
 * @author nik
 */
public class JavaModuleBuildTargetType extends BuildTargetType<ModuleBuildTarget> {
  public static final JavaModuleBuildTargetType PRODUCTION = new JavaModuleBuildTargetType("java-production", false);
  public static final JavaModuleBuildTargetType TEST = new JavaModuleBuildTargetType("java-test", true);
  public static final List<JavaModuleBuildTargetType> ALL_TYPES = Arrays.asList(PRODUCTION, TEST);

  private boolean myTests;

  private JavaModuleBuildTargetType(String typeId, boolean tests) {
    super(typeId);
    myTests = tests;
  }

  @NotNull
  @Override
  public List<ModuleBuildTarget> computeAllTargets(@NotNull JpsModel model) {
    List<JpsModule> modules = model.getProject().getModules();
    List<ModuleBuildTarget> targets = new ArrayList<ModuleBuildTarget>(modules.size());
    for (JpsModule module : modules) {
      targets.add(new ModuleBuildTarget(module, this));
    }
    return targets;
  }

  @NotNull
  @Override
  public Loader createLoader(@NotNull JpsModel model) {
    return new Loader(model);
  }

  public boolean isTests() {
    return myTests;
  }

  public static JavaModuleBuildTargetType getInstance(boolean tests) {
    return tests ? TEST : PRODUCTION;
  }

  private class Loader extends BuildTargetLoader<ModuleBuildTarget> {
    private final Map<String, JpsModule> myModules;

    public Loader(JpsModel model) {
      myModules = new HashMap<String, JpsModule>();
      for (JpsModule module : model.getProject().getModules()) {
        myModules.put(module.getName(), module);
      }
    }

    @Nullable
    @Override
    public ModuleBuildTarget createTarget(@NotNull String targetId) {
      JpsModule module = myModules.get(targetId);
      return module != null ? new ModuleBuildTarget(module, JavaModuleBuildTargetType.this) : null;
    }
  }
}
