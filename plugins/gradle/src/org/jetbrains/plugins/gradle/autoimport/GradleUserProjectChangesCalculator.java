/*
 * Copyright 2000-2013 JetBrains s.r.o.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.jetbrains.plugins.gradle.autoimport;

import com.intellij.openapi.module.Module;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.roots.*;
import com.intellij.openapi.roots.libraries.Library;
import com.intellij.openapi.util.Pair;
import com.intellij.openapi.util.Ref;
import com.intellij.openapi.util.text.StringUtil;
import com.intellij.util.Function;
import com.intellij.util.containers.ContainerUtil;
import com.intellij.util.containers.ContainerUtilRt;
import org.jetbrains.annotations.NotNull;
import org.jetbrains.annotations.Nullable;
import org.jetbrains.plugins.gradle.config.GradleLocalSettings;
import org.jetbrains.plugins.gradle.config.GradleSettings;
import org.jetbrains.plugins.gradle.config.PlatformFacade;
import org.jetbrains.plugins.gradle.model.gradle.*;
import org.jetbrains.plugins.gradle.sync.GradleProjectStructureHelper;
import org.jetbrains.plugins.gradle.util.GradleUtil;

import java.util.Map;
import java.util.Set;

/**
 * Encapsulates functionality of managing {@link GradleLocalSettings#getUserProjectChanges() explicit project structure changes made
 * by user}.
 * 
 * @author Denis Zhdanov
 * @since 2/19/13 9:27 AM
 */
public class GradleUserProjectChangesCalculator {

  @NotNull
  private static final Function<String, GradleUserProjectChange<?>> MODULE_ADDED = new Function<String, GradleUserProjectChange<?>>() {
    @Override
    public GradleUserProjectChange fun(String moduleName) {
      return new GradleAddModuleUserChange(moduleName);
    }
  };

  @NotNull
  private static final Function<String, GradleUserProjectChange<?>> MODULE_REMOVED = new Function<String, GradleUserProjectChange<?>>() {
    @Override
    public GradleUserProjectChange fun(String moduleName) {
      return new GradleRemoveModuleUserChange(moduleName);
    }
  };

  @NotNull private final PlatformFacade               myFacade;
  @NotNull private final GradleProjectStructureHelper myProjectStructureHelper;
  @NotNull private final Project                      myProject;
  @NotNull private final GradleLocalSettings          mySettings;

  @Nullable private GradleProject myLastProjectState;

  public GradleUserProjectChangesCalculator(@NotNull PlatformFacade facade,
                                            @NotNull GradleProjectStructureHelper helper, @NotNull Project project,
                                            @NotNull GradleLocalSettings settings)
  {
    myFacade = facade;
    myProjectStructureHelper = helper;
    myProject = project;
    mySettings = settings;
  }

  /**
   * Resets 'last known ide project state' to the current one.
   * 
   * @return    current ide project state
   * @see #updateChanges() 
   */
  @Nullable
  public GradleProject updateCurrentProjectState() {
    GradleProject state = buildCurrentIdeProject();
    myLastProjectState = state;
    filterOutdatedChanges();
    return state;
  }

  /**
   * This method is expected to be called every time manual project structure change is detected. It compares current project structure
   * with the {@link #updateCurrentProjectState() previous one} and considers all changes between them as user-made.
   * <p/>
   * All {@link GradleLocalSettings#getUserProjectChanges() old changes} are checked for validity and dropped if they are out of date.
   */
  public void updateChanges() {
    GradleProject lastProjectState = myLastProjectState;
    if (lastProjectState == null) {
      updateCurrentProjectState();
      return;
    }

    GradleProject currentProjectState = buildCurrentIdeProject();
    if (currentProjectState == null) {
      return;
    }
    
    Context context = new Context(lastProjectState, currentProjectState);

    buildModulePresenceChanges(context);
    buildDependencyPresenceChanges(context);
    filterOutdatedChanges();
    context.currentChanges.addAll(mySettings.getUserProjectChanges());
    mySettings.setUserProjectChanges(context.currentChanges);
    myLastProjectState = currentProjectState;
  }

  /**
   * We {@link GradleLocalSettings#getUserProjectChanges() keep a collection} of project structure changes explicitly made by a user.
   * It's possible, however, that some change might become outdated. Example:
   * <pre>
   * <ol>
   *   <li>New module is added to a project;</li>
   *   <li>Corresponding change is created;</li>
   *   <li>The module is removed from the project;</li>
   *   <li>The change is out of date now;</li>
   * </ol>
   * </pre>
   * This method removes all such outdated changes. 
   */
  public void filterOutdatedChanges() {
    Set<GradleUserProjectChange> changes = ContainerUtilRt.newHashSet(mySettings.getUserProjectChanges());
    for (GradleUserProjectChange change : mySettings.getUserProjectChanges()) {
      if (isUpToDate(change)) {
        change.setTimestamp(System.currentTimeMillis());
      }
      else {
        changes.remove(change);
      }
    }
    mySettings.setUserProjectChanges(changes);
  }

  private static void buildModulePresenceChanges(@NotNull final Context context) {
    buildChanges(context.oldModules.keySet(), context.currentModules.keySet(), MODULE_ADDED, MODULE_REMOVED, context);
  }

  private static void buildDependencyPresenceChanges(@NotNull Context context) {
    Set<String> commonModuleNames = ContainerUtilRt.newHashSet(context.currentModules.keySet());
    commonModuleNames.retainAll(context.oldModules.keySet());
    for (final String moduleName : commonModuleNames) {
      final Set<String> currentModuleDependencies = ContainerUtilRt.newHashSet();
      final Set<String> oldModuleDependencies = ContainerUtilRt.newHashSet();
      final Set<String> currentLibraryDependencies = ContainerUtilRt.newHashSet();
      final Set<String> oldLibraryDependencies = ContainerUtilRt.newHashSet();

      GradleEntityVisitor oldStateVisitor = new GradleEntityVisitorAdapter() {
        @Override
        public void visit(@NotNull GradleModuleDependency dependency) {
          oldModuleDependencies.add(dependency.getTarget().getName());
        }

        @Override
        public void visit(@NotNull GradleLibraryDependency dependency) {
          oldLibraryDependencies.add(dependency.getTarget().getName());
        }
      };
      for (GradleDependency dependency : context.oldModules.get(moduleName).getDependencies()) {
        dependency.invite(oldStateVisitor);
      }

      GradleEntityVisitor currentStateVisitor = new GradleEntityVisitorAdapter() {
        @Override
        public void visit(@NotNull GradleModuleDependency dependency) {
          currentModuleDependencies.add(dependency.getTarget().getName());
        }

        @Override
        public void visit(@NotNull GradleLibraryDependency dependency) {
          currentLibraryDependencies.add(dependency.getTarget().getName());
        }
      };
      for (GradleDependency dependency : context.currentModules.get(moduleName).getDependencies()) {
        dependency.invite(currentStateVisitor);
      }
      
      Function<String, GradleUserProjectChange<?>> addedModuleDependency = new Function<String, GradleUserProjectChange<?>>() {
        @Override
        public GradleUserProjectChange<?> fun(String s) {
          return new GradleAddModuleDependencyUserChange(moduleName, s);
        }
      };
      Function<String, GradleUserProjectChange<?>> removedModuleDependency = new Function<String, GradleUserProjectChange<?>>() {
        @Override
        public GradleUserProjectChange<?> fun(String s) {
          return new GradleRemoveModuleDependencyUserChange(moduleName, s);
        }
      };
      Function<String, GradleUserProjectChange<?>> addedLibraryDependency = new Function<String, GradleUserProjectChange<?>>() {
        @Override
        public GradleUserProjectChange<?> fun(String s) {
          return new GradleAddLibraryDependencyUserChange(moduleName, s);
        }
      };
      Function<String, GradleUserProjectChange<?>> removedLibraryDependency = new Function<String, GradleUserProjectChange<?>>() {
        @Override
        public GradleUserProjectChange<?> fun(String s) {
          return new GradleRemoveLibraryDependencyUserChange(moduleName, s);
        }
      };
      
      buildChanges(oldModuleDependencies, currentModuleDependencies, addedModuleDependency, removedModuleDependency, context);
      buildChanges(oldLibraryDependencies, currentLibraryDependencies, addedLibraryDependency, removedLibraryDependency, context);
    }
  }
  
  private static <T> void buildChanges(@NotNull Set<T> oldData,
                                       @NotNull Set<T> currentData,
                                       @NotNull Function<T,GradleUserProjectChange<?>> addChangeBuilder,
                                       @NotNull Function<T,GradleUserProjectChange<?>> removeChangeBuilder,
                                       @NotNull Context context)
  {
    Set<T> removed = ContainerUtilRt.newHashSet(oldData);
    removed.removeAll(currentData);
    if (!removed.isEmpty()) {
      for (final T r : removed) {
        context.currentChanges.add(removeChangeBuilder.fun(r));
      }
    }

    Set<T> added = ContainerUtilRt.newHashSet(currentData);
    added.removeAll(oldData);
    if (!added.isEmpty()) {
      for (final T a : added) {
        context.currentChanges.add(addChangeBuilder.fun(a));
      }
    }
  }
  
  @Nullable
  private GradleProject buildCurrentIdeProject() {
    GradleSettings settings = GradleSettings.getInstance(myProject);
    String linkedProjectPath = settings.getLinkedProjectPath();
    if (StringUtil.isEmpty(linkedProjectPath)) {
      return null;
    }

    String compileOutput = null;
    CompilerProjectExtension compilerProjectExtension = CompilerProjectExtension.getInstance(myProject);
    if (compilerProjectExtension != null) {
      compileOutput = compilerProjectExtension.getCompilerOutputUrl();
    }
    if (compileOutput == null) {
      compileOutput = "";
    }

    GradleProject result = new GradleProject(linkedProjectPath, compileOutput);
    final Map<String, GradleModule> modules = ContainerUtilRt.newHashMap();
    for (Module ideModule : myFacade.getModules(myProject)) {
      final GradleModule module = new GradleModule(ideModule.getName(), ideModule.getModuleFilePath());
      modules.put(module.getName(), module);
    }
    for (Module ideModule : myFacade.getModules(myProject)) {
      final GradleModule module = modules.get(ideModule.getName());
      RootPolicy<Void> visitor = new RootPolicy<Void>() {
        @Override
        public Void visitLibraryOrderEntry(LibraryOrderEntry libraryOrderEntry, Void value) {
          Library library = libraryOrderEntry.getLibrary();
          if (library != null) {
            module.addDependency(new GradleLibraryDependency(module, new GradleLibrary(GradleUtil.getLibraryName(library))));
          }
          return value;
        }

        @Override
        public Void visitModuleOrderEntry(ModuleOrderEntry moduleOrderEntry, Void value) {
          GradleModule dependencyModule = modules.get(moduleOrderEntry.getModuleName());
          if (dependencyModule != null) {
            module.addDependency(new GradleModuleDependency(module, dependencyModule));
          }
          return value;
        }
      };
      for (OrderEntry orderEntry : myFacade.getOrderEntries(ideModule)) {
        orderEntry.accept(visitor, null);
      }
      result.addModule(module);
    }
    
    return result;
  }

  /**
   * This method allows to answer if given change is up to date.
   * 
   * @param change  change to check
   * @return        <code>true</code> if given change is up to date; <code>false</code> otherwise
   * @see #filterOutdatedChanges()
   */
  private boolean isUpToDate(@NotNull GradleUserProjectChange<?> change) {
    final Ref<Boolean> result = new Ref<Boolean>();
    change.invite(new GradleUserProjectChangeVisitor() {
      @Override
      public void visit(@NotNull GradleAddModuleUserChange change) {
        String moduleName = change.getModuleName();
        assert moduleName != null;
        result.set(myProjectStructureHelper.findIdeModule(moduleName) != null);
      }

      @Override
      public void visit(@NotNull GradleRemoveModuleUserChange change) {
        String moduleName = change.getModuleName();
        assert moduleName != null;
        result.set(myProjectStructureHelper.findIdeModule(moduleName) == null); 
      }

      @Override
      public void visit(@NotNull GradleAddModuleDependencyUserChange change) {
        String moduleName = change.getModuleName();
        assert moduleName != null;
        String dependencyName = change.getDependencyName();
        assert dependencyName != null;
        result.set(myProjectStructureHelper.findIdeModuleDependency(moduleName, dependencyName) != null);
      }

      @Override
      public void visit(@NotNull GradleRemoveModuleDependencyUserChange change) {
        String moduleName = change.getModuleName();
        assert moduleName != null;
        String dependencyName = change.getDependencyName();
        assert dependencyName != null;
        result.set(myProjectStructureHelper.findIdeModuleDependency(moduleName, dependencyName) == null); 
      }

      @Override
      public void visit(@NotNull GradleAddLibraryDependencyUserChange change) {
        String moduleName = change.getModuleName();
        assert moduleName != null;
        String dependencyName = change.getDependencyName();
        assert dependencyName != null;
        result.set(myProjectStructureHelper.findIdeLibraryDependency(moduleName, dependencyName) != null); 
      }

      @Override
      public void visit(@NotNull GradleRemoveLibraryDependencyUserChange change) {
        String moduleName = change.getModuleName();
        assert moduleName != null;
        String dependencyName = change.getDependencyName();
        assert dependencyName != null;
        result.set(myProjectStructureHelper.findIdeLibraryDependency(moduleName, dependencyName) == null); 
      }
    });
    return result.get();
  }
  
  private static class Context {

    @NotNull public final Set<GradleUserProjectChange> currentChanges = ContainerUtilRt.newHashSet();

    @NotNull public final Map<String, GradleModule> oldModules;
    @NotNull public final Map<String, GradleModule> currentModules;

    Context(@NotNull GradleProject oldProjectState,
            @NotNull GradleProject currentProjectState)
    {
      Function<GradleModule, Pair<String, GradleModule>> modulesByName
        = new Function<GradleModule, Pair<String, GradleModule>>() {
        @Override
        public Pair<String, GradleModule> fun(GradleModule module) {
          return Pair.create(module.getName(), module);
        }
      };

      oldModules = ContainerUtil.map2Map(oldProjectState.getModules(), modulesByName);
      currentModules = ContainerUtil.map2Map(currentProjectState.getModules(), modulesByName);
    }
  }
}
