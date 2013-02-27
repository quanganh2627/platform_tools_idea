/*
 * Copyright 2006 ProductiveMe Inc.
 * Copyright 2013 JetBrains s.r.o.
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

package com.pme.launcher;

import org.apache.sanselan.ImageFormat;
import org.apache.sanselan.Sanselan;
import org.jdom.Document;
import org.jdom.input.SAXBuilder;

import java.awt.image.BufferedImage;
import java.io.*;
import java.nio.charset.Charset;
import java.util.HashMap;
import java.util.Map;
import java.util.Properties;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * @author yole
 */
public class LauncherGeneratorMain {
  public static void main(String[] args) {
    if (args.length != 5) {
      System.err.println("Usage: LauncherGeneratorMain <template EXE file> <app info file> <resource.h file> <properties> <output>");
      System.exit(1);
    }

    File template = new File(args[0]);
    if (!template.exists()) {
      System.err.println("Launcher template EXE file " + args[0] + " not found");
      System.exit(2);
    }

    InputStream appInfoStream = LauncherGeneratorMain.class.getClassLoader().getResourceAsStream(args[1]);
    if (appInfoStream == null) {
      System.err.println("Application info file " + appInfoStream + " not found");
      System.exit(3);
    }
    Document appInfo;
    try {
      appInfo = new SAXBuilder().build(appInfoStream);
    } catch (Exception e) {
      System.err.println("Error loading application info file " + args[1] + ": " + e.getMessage());
      System.exit(4);
      return;
    }

    String splashUrl = appInfo.getRootElement().getChild("logo").getAttributeValue("url");
    if (splashUrl.startsWith("/")) {
      splashUrl = splashUrl.substring(1);
    }
    InputStream splashStream = LauncherGeneratorMain.class.getClassLoader().getResourceAsStream(splashUrl);
    if (splashStream == null) {
      System.err.println("Splash screen image file file " + splashUrl + " not found");
      System.exit(5);
    }

    ByteArrayOutputStream splashBmpStream = new ByteArrayOutputStream();
    try {
      BufferedImage bufferedImage = Sanselan.getBufferedImage(splashStream);
      Sanselan.writeImage(bufferedImage, splashBmpStream, ImageFormat.IMAGE_FORMAT_BMP, new HashMap());
    }
    catch (Exception e) {
      System.err.println("Error converting splash screen to BMP: " + e.getMessage());
      System.exit(6);
    }

    String icoUrl = appInfo.getRootElement().getChild("icon").getAttributeValue("ico");
    if (icoUrl == null) {
      System.err.println(".ico file URL not specified in application info file " + args[1]);
      System.exit(11);
    }
    InputStream iconStream = LauncherGeneratorMain.class.getClassLoader().getResourceAsStream(icoUrl);
    if (iconStream == null) {
      System.err.println(".ico file " + icoUrl + " not found");
      System.exit(12);
    }

    Map<String, Integer> resourceIDs;
    try {
      resourceIDs = loadResourceIDs(args[2]);
    }
    catch (Exception e) {
      System.err.println("Error loading resource.h: " + e.getMessage());
      System.exit(7);
      return;
    }

    Properties properties = new Properties();
    try {
      FileInputStream fis = new FileInputStream(args[3]);
      try {
        properties.load(fis);
      }
      finally {
        fis.close();
      }
    }
    catch (IOException e) {
      System.err.println("Error loading launcher properties: " + e.getMessage());
      System.exit(8);
    }

    LauncherGenerator generator = new LauncherGenerator(template, new File(args[4]));
    try {
      generator.load();

      for (Map.Entry<Object, Object> pair : properties.entrySet()) {
        String key = (String) pair.getKey();
        Integer id = resourceIDs.get(key);
        if (id == null) {
          System.err.println("Invalid stringtable ID found: " + key);
          System.exit(9);
        }
        generator.setResourceString(id, (String) pair.getValue());
      }

      generator.injectBitmap(resourceIDs.get("IDB_SPLASH"), splashBmpStream.toByteArray());
      generator.injectIcon(resourceIDs.get("IDI_WINLAUNCHER"), iconStream);

      generator.generate();
    } catch (IOException e) {
      e.printStackTrace();
      System.exit(10);
    }
  }

  private static Map<String, Integer> loadResourceIDs(String arg) throws IOException {
    Map<String, Integer> result = new HashMap<String, Integer>();
    BufferedReader reader = new BufferedReader(new InputStreamReader(new FileInputStream(arg), Charset.forName("UTF-16")));
    Pattern pattern = Pattern.compile("#define (\\w+)\\s+(\\d+)");
    try {
      while(true) {
        String line = reader.readLine();
        if (line == null) break;
        Matcher m = pattern.matcher(line);
        if (m.matches()) {
          result.put(m.group(1), Integer.parseInt(m.group(2)));
        }
      }
    }
    finally {
      reader.close();
    }
    return result;
  }
}
