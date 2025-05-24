Architecture
Here's a list of the major components that make up PixiJS. Note that this list isn't exhaustive. Additionally, don't worry too much about how each component works. The goal here is to give you a feel for what's under the hood as we start exploring the engine.
Major Components
Component    Description
Renderer    The core of the PixiJS system is the renderer, which displays the scene graph and draws it to the screen. PixiJS will automatically determine whether to provide you the WebGPU or WebGL renderer under the hood.
Container    Main scene object which creates a scene graph: the tree of renderable objects to be displayed, such as sprites, graphics and text. See Scene Graph for more details.
Assets    The Asset system provides tools for asynchronously loading resources such as images and audio files.
Ticker    Tickers provide periodic callbacks based on a clock. Your game update logic will generally be run in response to a tick once per frame. You can have multiple tickers in use at one time.
Application    The Application is a simple helper that wraps a Loader, Ticker and Renderer into a single, convenient easy-to-use object. Great for getting started quickly, prototyping and building simple projects.
Events    PixiJS supports pointer-based interaction - making objects clickable, firing hover events, etc.
Accessibility    Woven through our display system is a rich set of tools for enabling keyboard and screen-reader accessibility.
Filters    PixiJS supports a variety of filters, including custom shaders, to apply effects to your renderable objects.
Extensions
PixiJS v8 is built entirely around the concept of extensions. Every system in PixiJS is implemented as a modular extension. This allows PixiJS to remain lightweight, flexible, and easy to extend.
info
In most cases, you won’t need to interact with the extension system directly unless you are developing a third-party library or contributing to the PixiJS ecosystem itself.
Extension Types
PixiJS supports a wide range of extension types, each serving a unique role in the architecture:
Assets
ExtensionType.Asset: Groups together loaders, resolvers, cache and detection extensions into one convenient object instead of having to register each one separately.
ExtensionType.LoadParser: Loads resources like images, JSON, videos.
ExtensionType.ResolveParser: Converts asset URLs into a format that can be used by the loader.
ExtensionType.CacheParser: Determines caching behavior for a particular asset.
ExtensionType.DetectionParser: Identifies asset format support on the current platform.
Renderer (WebGL, WebGPU, Canvas)
ExtensionType.WebGLSystem, ExtensionType.WebGPUSystem, ExtensionType.CanvasSystem: Add systems to their respective renderers. These systems can vary widely in functionality, from managing textures to accessibility features.
ExtensionType.WebGLPipes, ExtensionType.WebGPUPipes, ExtensionType.CanvasPipes: Add a new rendering pipe. RenderPipes are specifically used to render Renderables like a Mesh
ExtensionType.WebGLPipesAdaptor, ExtensionType.WebGPUPipesAdaptor, ExtensionType.CanvasPipesAdaptor: Adapt rendering pipes for the respective renderers.
Application
ExtensionType.Application: Used for plugins that extend the Application lifecycle. For example the TickerPlugin and ResizePlugin are both application extensions.
Environment
ExtensionType.Environment: Used to detect and configure platform-specific behavior. This can be useful for configuring PixiJS to work in environments like Node.js, Web Workers, or the browser.
Other (Primarily Internal Use)
These extension types are mainly used internally and are typically not required in most user-facing applications:
ExtensionType.MaskEffect: Used by MaskEffectManager for custom masking behaviors.
ExtensionType.BlendMode: A type of extension for creating a new advanced blend mode.
ExtensionType.TextureSource: A type of extension that will be used to auto detect a resource type E.g VideoSource
ExtensionType.ShapeBuilder: A type of extension for building and triangulating custom shapes used in graphics.
ExtensionType.Batcher: A type of extension for creating custom batchers used in rendering.Scene Graph
Every frame, PixiJS is updating and then rendering the scene graph. Let's talk about what's in the scene graph, and how it impacts how you develop your project. If you've built games before, this should all sound very familiar, but if you're coming from HTML and the DOM, it's worth understanding before we get into specific types of objects you can render.
The Scene Graph Is a Tree
The scene graph's root node is a container maintained by the application, and referenced with app.stage. When you add a sprite or other renderable object as a child to the stage, it's added to the scene graph and will be rendered and interactable. PixiJS Containers can also have children, and so as you build more complex scenes, you will end up with a tree of parent-child relationships, rooted at the app's stage.
(A helpful tool for exploring your project is the Pixi.js devtools plugin for Chrome, which allows you to view and manipulate the scene graph in real time as it's running!)
Parents and Children
When a parent moves, its children move as well. When a parent is rotated, its children are rotated too. Hide a parent, and the children will also be hidden. If you have a game object that's made up of multiple sprites, you can collect them under a container to treat them as a single object in the world, moving and rotating as one.
Each frame, PixiJS runs through the scene graph from the root down through all the children to the leaves to calculate each object's final position, rotation, visibility, transparency, etc. If a parent's alpha is set to 0.5 (making it 50% transparent), all its children will start at 50% transparent as well. If a child is then set to 0.5 alpha, it won't be 50% transparent, it will be 0.5 x 0.5 = 0.25 alpha, or 75% transparent. Similarly, an object's position is relative to its parent, so if a parent is set to an x position of 50 pixels, and the child is set to an x position of 100 pixels, it will be drawn at a screen offset of 150 pixels, or 50 + 100.
Here's an example. We'll create three sprites, each a child of the last, and animate their position, rotation, scale and alpha. Even though each sprite's properties are set to the same values, the parent-child chain amplifies each change:
1
import { A
Editor
Preview
Both
The cumulative translation, rotation, scale and skew of any given node in the scene graph is stored in the object's worldTransform property. Similarly, the cumulative alpha value is stored in the worldAlpha property.
Render Order
So we have a tree of things to draw. Who gets drawn first?
PixiJS renders the tree from the root down. At each level, the current object is rendered, then each child is rendered in order of insertion. So the second child is rendered on top of the first child, and the third over the second.
Check out this example, with two parent objects A & D, and two children B & C under A:
1
import { A
Editor
Preview
Both
If you'd like to re-order a child object, you can use setChildIndex(). To add a child at a given point in a parent's list, use addChildAt(). Finally, you can enable automatic sorting of an object's children using the sortableChildren option combined with setting the zIndex property on each child.
RenderGroups
As you delve deeper into PixiJS, you'll encounter a powerful feature known as Render Groups. Think of Render Groups as specialized containers within your scene graph that act like mini scene graphs themselves. Here's what you need to know to effectively use Render Groups in your projects. For more info check out the RenderGroups overview
Culling
If you're building a project where a large proportion of your scene objects are off-screen (say, a side-scrolling game), you will want to cull those objects. Culling is the process of evaluating if an object (or its children!) is on the screen, and if not, turning off rendering for it. If you don't cull off-screen objects, the renderer will still draw them, even though none of their pixels end up on the screen.
PixiJS provides built-in support for viewport culling. To enable culling, set cullable = true on your objects. You can also set cullableChildren to false to allow PixiJS to bypass the recursive culling function, which can improve performance. Additionally, you can set cullArea to further optimize performance by defining the area to be culled.
Local vs Global Coordinates
If you add a sprite to the stage, by default it will show up in the top left corner of the screen. That's the origin of the global coordinate space used by PixiJS. If all your objects were children of the stage, that's the only coordinates you'd need to worry about. But once you introduce containers and children, things get more complicated. A child object at [50, 100] is 50 pixels right and 100 pixels down from its parent.
We call these two coordinate systems "global" and "local" coordinates. When you use position.set(x, y) on an object, you're always working in local coordinates, relative to the object's parent.
The problem is, there are many times when you want to know the global position of an object. For example, if you want to cull offscreen objects to save render time, you need to know if a given child is outside the view rectangle.
To convert from local to global coordinates, you use the toGlobal() function. Here's a sample usage:
// Get the global position of an object, relative to the top-left of the screen
let globalPos = obj.toGlobal(new Point(0,0));
This snippet will set globalPos to be the global coordinates for the child object, relative to [0, 0] in the global coordinate system.
Global vs Screen Coordinates
When your project is working with the host operating system or browser, there is a third coordinate system that comes into play - "screen" coordinates (aka "viewport" coordinates). Screen coordinates represent position relative to the top-left of the canvas element that PixiJS is rendering into. Things like the DOM and native mouse click events work in screen space.
Now, in many cases, screen space is equivalent to world space. This is the case if the size of the canvas is the same as the size of the render view specified when you create you Application. By default, this will be the case - you'll create for example an 800x600 application window and add it to your HTML page, and it will stay that size. 100 pixels in world coordinates will equal 100 pixels in screen space. BUT! It is common to stretch the rendered view to have it fill the screen, or to render at a lower resolution and up-scale for speed. In that case, the screen size of the canvas element will change (e.g. via CSS), but the underlying render view will not, resulting in a mis-match between world coordinates and screen coordinates.
Render Loop
At the core of PixiJS lies its render loop, a repeating cycle that updates and redraws your scene every frame. Unlike traditional web development where rendering is event-based (e.g. on user input), PixiJS uses a continuous animation loop that provides full control over real-time rendering.
This guide provides a deep dive into how PixiJS structures this loop internally, from the moment a frame begins to when it is rendered to the screen. Understanding this will help you write more performant, well-structured applications.
Overview
Each frame, PixiJS performs the following sequence:
Tickers are executed (user logic)
Scene graph is updated (transforms and culling)
Rendering occurs (GPU draw calls)
This cycle repeats as long as your application is running and its ticker is active.
Step 1: Running Ticker Callbacks
The render loop is driven by the Ticker class, which uses requestAnimationFrame to schedule work. Each tick:
Measures elapsed time since the previous frame
Caps it based on minFPS and maxFPS
Calls every listener registered with ticker.add() or app.ticker.add()
Example
app.ticker.add((ticker) => {
    bunny.rotation += ticker.deltaTime * 0.1;
});
Every callback receives the current Ticker instance. You can access ticker.deltaTime (scaled frame delta) and ticker.elapsedMS (unscaled delta in ms) to time animations.
Step 2: Updating the Scene Graph
PixiJS uses a hierarchical scene graph to represent all visual objects. Before rendering, the graph needs to be traversed to:
Recalculate transforms (world matrix updates)
Apply custom logic via onRender handlers
Apply culling if enabled
Step 3: Rendering the Scene
Once the scene graph is ready, the renderer walks the display list starting at app.stage:
Applies global and local transformations
Batches draw calls when possible
Uploads geometry, textures, and uniforms
Issues GPU commands
All rendering is retained mode: objects persist across frames unless explicitly removed.
Rendering is done via either WebGL or WebGPU, depending on your environment. The renderer abstracts away the differences behind a common API.
Full Frame Lifecycle Diagram
requestAnimationFrame
        │
    [Ticker._tick()]
        │
    ├─ Compute elapsed time
    ├─ Call user listeners
    │   └─ sprite.onRender
    ├─ Cull display objects (if enabled)
    ├─ Update world transforms
    └─ Render stage
            ├─ Traverse display list
            ├─ Upload data to GPU
            └─ Draw

Render Groups
Understanding RenderGroups in PixiJS
As you delve deeper into PixiJS, especially with version 8, you'll encounter a powerful feature known as RenderGroups. Think of RenderGroups as specialized containers within your scene graph that act like mini scene graphs themselves. Here's what you need to know to effectively use Render Groups in your projects:
What Are Render Groups?
Render Groups are essentially containers that PixiJS treats as self-contained scene graphs. When you assign parts of your scene to a Render Group, you're telling PixiJS to manage these objects together as a unit. This management includes monitoring for changes and preparing a set of render instructions specifically for the group. This is a powerful tool for optimizing your rendering process.
Why Use Render Groups?
The main advantage of using Render Groups lies in their optimization capabilities. They allow for certain calculations, like transformations (position, scale, rotation), tint, and alpha adjustments, to be offloaded to the GPU. This means that operations like moving or adjusting the Render Group can be done with minimal CPU impact, making your application more performance-efficient.
In practice, you're utilizing Render Groups even without explicit awareness. The root element you pass to the render function in PixiJS is automatically converted into a RenderGroup as this is where its render instructions will be stored. Though you also have the option to explicitly create additional RenderGroups as needed to further optimize your project.
This feature is particularly beneficial for:
Static Content: For content that doesn't change often, a Render Group can significantly reduce the computational load on the CPU. In this case static refers to the scene graph structure, not that actual values of the PixiJS elements inside it (eg position, scale of things).
Distinct Scene Parts: You can separate your scene into logical parts, such as the game world and the HUD (Heads-Up Display). Each part can be optimized individually, leading to overall better performance.
Examples
const myGameWorld = new Container({
  isRenderGroup:true
})
const myHud = new Container({
  isRenderGroup:true
})
scene.addChild(myGameWorld, myHud)
renderer.render(scene) // this action will actually convert the scene to a render group under the hood
Check out the container example.
Best Practices
Don't Overuse: While Render Groups are powerful, using too many can actually degrade performance. The goal is to find a balance that optimizes rendering without overwhelming the system with too many separate groups. Make sure to profile when using them. The majority of the time you won't need to use them at all!
Strategic Grouping: Consider what parts of your scene change together and which parts remain static. Grouping dynamic elements separately from static elements can lead to performance gains.
By understanding and utilizing Render Groups, you can take full advantage of PixiJS's rendering capabilities, making your applications smoother and more efficient. This feature represents a powerful tool in the optimization toolkit offered by PixiJS, enabling developers to create rich, interactive scenes that run smoothly across different devices. Render Layers The PixiJS Layer API provides a powerful way to control the rendering order of objects independently of their logical parent-child relationships in the scene graph. With RenderLayers, you can decouple how objects are transformed (via their logical parent) from how they are visually drawn on the screen. Using RenderLayers ensures these elements are visually prioritized while maintaining logical parent-child relationships. Examples include: A character with a health bar: Ensure the health bar always appears on top of the world, even if the character moves behind an object. UI elements like score counters or notifications: Keep them visible regardless of the game world’s complexity. Highlighting Elements in Tutorials: Imagine a tutorial where you need to push back most game elements while highlighting a specific object. RenderLayers can split these visually. The highlighted object can be placed in a foreground layer to be rendered above a push back layer. This guide explains the key concepts, provides practical examples, and highlights common gotchas to help you use the Layer API effectively. Key Concepts Independent Rendering Order: RenderLayers allow control of the draw order independently of the logical hierarchy, ensuring objects are rendered in the desired order. Logical Parenting Stays Intact: Objects maintain transformations (e.g., position, scale, rotation) from their logical parent, even when attached to RenderLayers. Explicit Object Management: Objects must be manually reassigned to a layer after being removed from the scene graph or layer, ensuring deliberate control over rendering. Dynamic Sorting: Within layers, objects can be dynamically reordered using zIndex and sortChildren for fine-grained control of rendering order. Basic API Usage First lets create two items that we want to render, red guy and blue guy. const redGuy = new PIXI.Sprite('red guy'); redGuy.tint = 0xff0000; const blueGuy = new PIXI.Sprite('blue guy'); blueGuy.tint = 0x0000ff; stage.addChild(redGuy, blueGuy); alt text Now we know that red guy will be rendered first, then blue guy. Now in this simple example you could get away with just sorting the zIndex of the red guy and blue guy to help reorder. But this is a guide about render layers, so lets create one of those. Use renderLayer.attach to assign an object to a layer. This overrides the object’s default render order defined by its logical parent. // a layer.. const layer = new RenderLayer(); stage.addChild(layer); layer.attach(redGuy); alt text So now our scene graph order is: |- stage |-- redGuy |-- blueGuy |-- layer And our render order is: |- stage |-- blueGuy |-- layer |-- redGuy This happens because the layer is now the last child in the stage. Since the red guy is attached to the layer, it will be rendered at the layer's position in the scene graph. However, it still logically remains in the same place in the scene hierarchy. 3. Removing Objects from a Layer Now let's remove the red guy from the layer. To stop an object from being rendered in a layer, use removeFromLayer. Once removed from the layer, its still going to be in the scene graph, and will be rendered in its scene graph order. layer.detach(redGuy); //  Stop rendering the rect via the layer alt text Removing an object from its logical parent (removeChild) automatically removes it from the layer. stage.removeChild(redGuy); // if the red guy was removed from the stage, it will also be removed from the layer alt text However, if you remove the red guy from the stage and then add it back to the stage, it will not be added to the layer again. // add red guy to his original position stage.addChildAt(redGuy, 0); alt text You will need to reattach it to the layer yourself. layer.attach(redGuy); // re attach it to the layer again! alt text This may seem like a pain, but it's actually a good thing. It means that you have full control over the render order of the object, and you can change it at any time. It also means you can't accidentally add an object to a container and have it automatically re-attach to a layer that may or may not still be around - it would be quite confusing and lead to some very hard to debug bugs! 5. Layer Position in Scene Graph The layer’s position in the scene graph determines its render priority relative to other layers and objects. // reparent the layer to render first in the stage stage.addChildAt(layer, 0); alt text Complete Example Here’s a real-world example that shows how to use RenderLayers to set ap player ui on top of the world. 1 import { A Editor Preview Both Gotchas and Things to Watch Out For Manual Reassignment: When an object is re-added to a logical parent, it does not automatically reassociate with its previous layer. Always reassign the object to the layer explicitly. Nested Children: If you remove a parent container, all its children are automatically removed from layers. Be cautious with complex hierarchies. Sorting Within Layers: Objects in a layer can be sorted dynamically using their zIndex property. This is useful for fine-grained control of render order. rect.zIndex = 10; // Higher values render later layer.sortableChildren = true; // Enable sorting layer.sortRenderLayerChildren(); // Apply the sorting Layer Overlap: If multiple layers overlap, their order in the scene graph determines the render priority. Ensure the layering logic aligns with your desired visual output. Best Practices Group Strategically: Minimize the number of layers to optimize performance. Use for Visual Clarity: Reserve layers for objects that need explicit control over render order. Test Dynamic Changes: Verify that adding, removing, or reassigning objects to layers behaves as expected in your specific scene setup. By understanding and leveraging RenderLayers effectively, you can achieve precise control over your scene's visual presentation while maintaining a clean and logical hierarchy.Textures
Textures are one of the most essential components in the PixiJS rendering pipeline. They define the visual content used by Sprites, Meshes, and other renderable objects. This guide covers how textures are loaded, created, and used, along with the various types of data sources PixiJS supports.
Texture Lifecycle
The texture system is built around two major classes:
TextureSource: Represents a pixel source, such as an image, canvas, or video.
Texture: Defines a view into a TextureSource, including sub-rectangles, trims, and transformations.
Lifecycle Flow
Source File/Image -> TextureSource -> Texture -> Sprite (or other display object)
Loading Textures
Textures can be loaded asynchronously using the Assets system:
const texture = await Assets.load('myTexture.png');
const sprite = new Sprite(texture);
Preparing Textures
Even after you've loaded your textures, the images still need to be pushed to the GPU and decoded. Doing this for a large number of source images can be slow and cause lag spikes when your project first loads. To solve this, you can use the Prepare plugin, which allows you to pre-load textures in a final step before displaying your project.
Texture vs. TextureSource
The TextureSource handles the raw pixel data and GPU upload. A Texture is a lightweight view on that source, with metadata such as trimming, frame rectangle, UV mapping, etc. Multiple Texture instances can share a single TextureSource, such as in a sprite sheet.
const sheet = await Assets.load('spritesheet.json');
const heroTexture = sheet.textures['hero.png'];
Texture Creation
You can manually create textures using the constructor:
const mySource = new TextureSource({ resource: myImage });
const texture = new Texture({ source: mySource });
Set dynamic: true in the Texture options if you plan to modify its frame, trim, or source at runtime.
Destroying Textures
Once you're done with a Texture, you may wish to free up the memory (both WebGL-managed buffers and browser-based) that it uses. To do so, you should call Assets.unload('texture.png'), or texture.destroy() if you have created the texture outside of Assets.
This is a particularly good idea for short-lived imagery like cut-scenes that are large and will only be used once. If a texture is destroyed that was loaded via Assets then the assets class will automatically remove it from the cache for you.
Unload Texture from GPU
If you want to unload a texture from the GPU but keep it in memory, you can call texture.source.unload(). This will remove the texture from the GPU but keep the source in memory.
// Load the texture
const texture = await Assets.load('myTexture.png');
// ... Use the texture
// Unload the texture from the GPU
texture.source.unload();
Texture Types
PixiJS supports multiple TextureSource types, depending on the kind of input data:
Texture Type    Description
ImageSource    HTMLImageElement, ImageBitmap, SVG's, VideoFrame, etc.
CanvasSource    HTMLCanvasElement or OffscreenCanvas
VideoSource    HTMLVideoElement with optional auto-play and update FPS
BufferImageSource    TypedArray or ArrayBuffer with explicit width, height, and format
CompressedSource    Array of compressed mipmaps (Uint8Array[])
Common Texture Properties
Here are some important properties of the Texture class:
frame: Rectangle defining the visible portion within the source.
orig: Original untrimmed dimensions.
trim: Defines trimmed regions to exclude transparent space.
uvs: UV coordinates generated from frame and rotate.
rotate: GroupD8 rotation value for atlas compatibility.
defaultAnchor: Default anchor when used in Sprites.
defaultBorders: Used for 9-slice scaling.
source: The TextureSource instance.
Common TextureSource Properties
Here are some important properties of the TextureSource class:
resolution: Affects render size relative to actual pixel size.
format: Texture format (e.g., rgba8unorm, bgra8unorm, etc.)
alphaMode: Controls how alpha is interpreted on upload.
wrapMode / scaleMode: Controls how texture is sampled outside of bounds or when scaled.
autoGenerateMipmaps: Whether to generate mipmaps on upload.
You can set these properties when creating a TextureSource:
texture.source.scaleMode = 'linear';
texture.source.wrapMode = 'repeat';
Container
The Container class is the foundation of PixiJS's scene graph system. Containers act as groups of scene objects, allowing you to build complex hierarchies, organize rendering layers, and apply transforms or effects to groups of objects.
What Is a Container?
A Container is a general-purpose node that can hold other display objects, including other containers. It is used to structure your scene, apply transformations, and manage rendering and interaction.
Containers are not rendered directly. Instead, they delegate rendering to their children.
import { Container, Sprite } from 'pixi.js';
const group = new Container();
const sprite = Sprite.from('bunny.png');
group.addChild(sprite);
Managing Children
PixiJS provides a robust API for adding, removing, reordering, and swapping children in a container:
const container = new Container();
const child1 = new Container();
const child2 = new Container();
container.addChild(child1, child2);
container.removeChild(child1);
container.addChildAt(child1, 0);
container.swapChildren(child1, child2);
You can also remove a child by index or remove all children within a range:
container.removeChildAt(0);
container.removeChildren(0, 2);
To keep a child’s world transform while moving it to another container, use reparentChild or reparentChildAt:
otherContainer.reparentChild(child);
Events
Containers emit events when children are added or removed:
group.on('childAdded', (child, parent, index) => { ... });
group.on('childRemoved', (child, parent, index) => { ... });
Finding Children
Containers support searching children by label using helper methods:
const child = new Container({ label: 'enemy' });
container.addChild(child);
container.getChildByLabel('enemy');
container.getChildrenByLabel(/^enemy/); // all children whose label starts with "enemy"
Set deep = true to search recursively through all descendants.
container.getChildByLabel('ui', true);
Sorting Children
Use zIndex and sortableChildren to control render order within a container:
child1.zIndex = 1;
child2.zIndex = 10;
container.sortableChildren = true;
Call sortChildren() to manually re-sort if needed:
container.sortChildren();
info
Use this feature sparingly, as sorting can be expensive for large numbers of children.
Optimizing with Render Groups
Containers can be promoted to render groups by setting isRenderGroup = true or calling enableRenderGroup().
Use render groups for UI layers, particle systems, or large moving subtrees. See the Render Groups guide for more details.
const uiLayer = new Container({ isRenderGroup: true });
Cache as Texture
The cacheAsTexture function in PixiJS is a powerful tool for optimizing rendering in your applications. By rendering a container and its children to a texture, cacheAsTexture can significantly improve performance for static or infrequently updated containers.
When you set container.cacheAsTexture(), the container is rendered to a texture. Subsequent renders reuse this texture instead of rendering all the individual children of the container. This approach is particularly useful for containers with many static elements, as it reduces the rendering workload.
Note
cacheAsTexture is PixiJS v8's equivalent of the previous cacheAsBitmap functionality. If you're migrating from v7 or earlier, simply replace cacheAsBitmap with cacheAsTexture in your code.
const container = new Container();
const sprite = Sprite.from('bunny.png');
container.addChild(sprite);
// enable cache as texture
container.cacheAsTexture();
// update the texture if the container changes
container.updateCacheTexture();
// disable cache as texture
container.cacheAsTexture(false);
For more advanced usage, including setting cache options and handling dynamic content, refer to the Cache as Texture guide.Cache As Texture
Using cacheAsTexture in PixiJS
The cacheAsTexture function in PixiJS is a powerful tool for optimizing rendering in your applications. By rendering a container and its children to a texture, cacheAsTexture can significantly improve performance for static or infrequently updated containers. Let's explore how to use it effectively, along with its benefits and considerations.
Note
cacheAsTexture is PixiJS v8's equivalent of the previous cacheAsBitmap functionality. If you're migrating from v7 or earlier, simply replace cacheAsBitmap with cacheAsTexture in your code.
What Is cacheAsTexture?
When you set container.cacheAsTexture(), the container is rendered to a texture. Subsequent renders reuse this texture instead of rendering all the individual children of the container. This approach is particularly useful for containers with many static elements, as it reduces the rendering workload.
To update the texture after making changes to the container, call:
container.updateCacheTexture();
and to turn it off, call:
container.cacheAsTexture(false);
Basic Usage
Here's an example that demonstrates how to use cacheAsTexture:
import * as PIXI from 'pixi.js';
(async () =>
{
    // Create a new application
    const app = new Application();
    // Initialize the application
    await app.init({ background: '
#1099bb', resizeTo: window });
    // Append the application canvas to the document body
    document.body.appendChild(app.canvas);
    // load sprite sheet..
    await Assets.load('https://pixijs.com/assets/spritesheet/monsters.json');
    // holder to store aliens
    const aliens = [];
    const alienFrames = ['eggHead.png', 'flowerTop.png', 'helmlok.png', 'skully.png'];
    let count = 0;
    // create an empty container
    const alienContainer = new Container();
    alienContainer.x = 400;
    alienContainer.y = 300;
    app.stage.addChild(alienContainer);
    // add a bunch of aliens with textures from image paths
    for (let i = 0; i < 100; i++)
    {
        const frameName = alienFrames[i % 4];
        // create an alien using the frame name..
        const alien = Sprite.from(frameName);
        alien.tint = Math.random() * 0xffffff;
        alien.x = Math.random() * 800 - 400;
        alien.y = Math.random() * 600 - 300;
        alien.anchor.x = 0.5;
        alien.anchor.y = 0.5;
        aliens.push(alien);
        alienContainer.addChild(alien);
    }
    // this will cache the container and its children as a single texture
    // so instead of drawing 100 sprites, it will draw a single texture!
    alienContainer.cacheAsTexture()
})();
In this example, the container and its children are rendered to a single texture, reducing the rendering overhead when the scene is drawn.
Play around with the example here.
Advanced Usage
Instead of enabling cacheAsTexture with true, you can pass a configuration object which is very similar to texture source options.
container.cacheAsTexture({
    resolution: 2,
    antialias: true,
});
resolution is the resolution of the texture. By default this is the same as you renderer or application.
antialias is the antialias mode to use for the texture. Much like the resolution this defaults to the renderer or application antialias mode.
Benefits of cacheAsTexture
Performance Boost: Rendering a complex container as a single texture avoids the need to process each child element individually during each frame.
Optimized for Static Content: Ideal for containers with static or rarely updated children.
Advanced Details
Memory Tradeoff: Each cached texture requires GPU memory. Using cacheAsTexture trades rendering speed for increased memory usage.
GPU Limitations: If your container is too large (e.g., over 4096x4096 pixels), the texture may fail to cache, depending on GPU limitations.
How It Works Internally
Under the hood, cacheAsTexture converts the container into a render group and renders it to a texture. It uses the same texture cache mechanism as filters:
container.enableRenderGroup();
container.renderGroup.cacheAsTexture = true;
Once the texture is cached, updating it via updateCacheTexture() is efficient and incurs minimal overhead. Its as fast as rendering the container normally.
Best Practices
DO:
Use for Static Content: Apply cacheAsTexture to containers with elements that don't change frequently, such as a UI panel with static decorations.
Leverage for Performance: Use cacheAsTexture to render complex containers as a single texture, reducing the overhead of processing each child element individually every frame. This is especially useful for containers that contain expensive effects eg filters.
Switch of Antialiasing: setting antialiasing to false can give a small performance boost, but the texture may look a bit more pixelated around its children's edges.
Resolution: Do adjust the resolution based on your situation, if something is scaled down, you can use a lower resolution.If something is scaled up, you may want to use a higher resolution. But be aware that the higher the resolution the larger the texture and memory footprint.
DON'T:
Apply to Very Large Containers: Avoid using cacheAsTexture on containers that are too large (e.g., over 4096x4096 pixels), as they may fail to cache due to GPU limitations. Instead, split them into smaller containers.
Overuse for Dynamic Content: Flick cacheAsTexture on / off frequently on containers, as this results in constant re-caching, negating its benefits. Its better to Cache as texture when you once, and then use updateCacheTexture to update it.
Apply to Sparse Content: Do not use cacheAsTexture for containers with very few elements or sparse content, as the performance improvement will be negligible.
Ignore Memory Impact: Be cautious of GPU memory usage. Each cached texture consumes memory, so overusing cacheAsTexture can lead to resource constraints.
Gotchas
Rendering Depends on Scene Visibility: The cache updates only when the containing scene is rendered. Modifying the layout after setting cacheAsTexture but before rendering your scene will be reflected in the cache.
Containers are rendered with no transform: Cached items are rendered at their actual size, ignoring transforms like scaling. For instance, an item scaled down by 50%, its texture will be cached at 100% size and then scaled down by the scene.
Caching and Filters: Filters may not behave as expected with cacheAsTexture. To cache the filter effect, wrap the item in a parent container and apply cacheAsTexture to the parent.
Reusing the texture: If you want to create a new texture based on the container, its better to use const texture = renderer.generateTexture(container) and share that amongst you objects!
By understanding and applying cacheAsTexture strategically, you can significantly enhance the rendering performance of your PixiJS projects. Happy coding!Sprite
Sprites are the foundational visual elements in PixiJS. They represent a single image to be displayed on the screen. Each Sprite contains a Texture to be drawn, along with all the transformation and display state required to function in the scene graph.
import { Assets, Sprite } from 'pixi.js';
const texture = await Assets.load('path/to/image.png');
const sprite = new Sprite(texture);
sprite.anchor.set(0.5);
sprite.position.set(100, 100);
sprite.scale.set(2);
sprite.rotation = Math.PI / 4; // Rotate 45 degrees
Updating the Texture
If you change the texture of a sprite, it will automatically:
Rebind listeners for texture updates
Recalculate width/height if set so that the visual size remains the same
Trigger a visual update
const texture = Assets.get('path/to/image.png');
sprite.texture = texture;
Scale vs Width/Height
Sprites inherit scale from Container, allowing for percentage-based resizing:
sprite.scale.set(2); // Double the size
Sprites also have width and height properties that act as convenience setters for scale, based on the texture’s dimensions:
sprite.width = 100; // Automatically updates scale.x
// sets: sprite.scale.x = 100 / sprite.texture.orig.width;
Particle Container
ixiJS v8 introduces a high-performance particle system via the ParticleContainer and Particle classes. Designed for rendering vast numbers of lightweight visuals—like sparks, bubbles, bunnies, or explosions—this system provides raw speed by stripping away all non-essential overhead.
Experimental API Notice
The Particle API is stable but experimental. Its interface may evolve in future PixiJS versions. We welcome feedback to help guide its development.
import { ParticleContainer, Particle, Texture } from 'pixi.js';
const texture = Texture.from('bunny.png');
const container = new ParticleContainer({
    dynamicProperties: {
        position: true, // default
        scale: false,
        rotation: false,
        color: false,
    },
});
for (let i = 0; i < 100000; i++) {
    const particle = new Particle({
        texture,
        x: Math.random() * 800,
        y: Math.random() * 600,
    });
    container.addParticle(particle);
}
app.stage.addChild(container);
Why Use ParticleContainer?
Extreme performance: Render hundreds of thousands or even millions of particles with high FPS.
Lightweight design: Particles are more efficient than Sprite, lacking extra features like children, events, or filters.
Fine-grained control: Optimize rendering by declaring which properties are dynamic (updated every frame) or static (set once).
Performance Tip: Static vs. Dynamic
Dynamic properties are uploaded to the GPU every frame.
Static properties are uploaded only when update() is called.
Declare your needs explicitly:
const container = new ParticleContainer({
    dynamicProperties: {
        position: true,
        rotation: true,
        scale: false,
        color: false,
    },
});
If you later modify a static property or the particle list, you must call:
container.update();
Limitations and API Differences
ParticleContainer is designed for speed and simplicity. As such, it doesn't support the full Container API:
❌ Not Available:
addChild(), removeChild()
getChildAt(), setChildIndex()
swapChildren(), reparentChild()
✅ Use Instead:
addParticle(particle)
removeParticle(particle)
removeParticles(beginIndex, endIndex)
addParticleAt(particle, index)
removeParticleAt(index)
These methods operate on the .particleChildren array and maintain the internal GPU buffers correctly.
Creating a Particle
A Particle supports key display properties, and is far more efficient than Sprite.
Particle Example
const particle = new Particle({
    texture: Texture.from('spark.png'),
    x: 200,
    y: 100,
    scaleX: 0.8,
    scaleY: 0.8,
    rotation: Math.PI / 4,
    tint: 0xff0000,
    alpha: 0.5,
});
You can also use the shorthand:
const particle = new Particle(Texture.from('spark.png'));
Events / Interaction
PixiJS is primarily a rendering library, but it provides a flexible and performant event system designed for both mouse and touch input. This system replaces the legacy InteractionManager from previous versions with a unified, DOM-like federated event model.
const sprite = new Sprite(texture);
sprite.eventMode = 'static';
sprite.on('pointerdown', () => {
    console.log('Sprite clicked!');
});
Event Modes
To use the event system, set the eventMode of a Container (or its subclasses like Sprite) and subscribe to event listeners.
The eventMode property controls how an object interacts with the event system:
Mode    Description
none    Ignores all interaction events, including children. Optimized for non-interactive elements.
passive    (default) Ignores self-hit testing and does not emit events, but interactive children still receive events.
auto    Participates in hit testing only if a parent is interactive. Does not emit events.
static    Emits events and is hit tested. Suitable for non-moving interactive elements like buttons.
dynamic    Same as static, but also receives synthetic events when the pointer is idle. Suitable for animating or moving targets.
Event Types
PixiJS supports a rich set of DOM-like event types across mouse, touch, and pointer input. Below is a categorized list.
Pointer Events (Recommended for general use)
Event Type    Description
pointerdown    Fired when a pointer (mouse, pen, or touch) is pressed on a display object.
pointerup    Fired when the pointer is released over the display object.
pointerupoutside    Fired when the pointer is released outside the object that received pointerdown.
pointermove    Fired when the pointer moves over the display object.
pointerover    Fired when the pointer enters the boundary of the display object.
pointerout    Fired when the pointer leaves the boundary of the display object.
pointerenter    Fired when the pointer enters the display object (does not bubble).
pointerleave    Fired when the pointer leaves the display object (does not bubble).
pointercancel    Fired when the pointer interaction is canceled (e.g. touch lost).
pointertap    Fired when a pointer performs a quick tap.
globalpointermove    Fired on every pointer move, regardless of whether any display object is hit.
Mouse Events (Used for mouse-specific input)
Event Type    Description
mousedown    Fired when a mouse button is pressed on a display object.
mouseup    Fired when a mouse button is released over the object.
mouseupoutside    Fired when a mouse button is released outside the object that received mousedown.
mousemove    Fired when the mouse moves over the display object.
mouseover    Fired when the mouse enters the display object.
mouseout    Fired when the mouse leaves the display object.
mouseenter    Fired when the mouse enters the object, does not bubble.
mouseleave    Fired when the mouse leaves the object, does not bubble.
click    Fired when a mouse click (press and release) occurs on the object.
rightdown    Fired when the right mouse button is pressed on the display object.
rightup    Fired when the right mouse button is released over the object.
rightupoutside    Fired when the right mouse button is released outside the object that received rightdown.
rightclick    Fired when a right mouse click (press and release) occurs on the object.
globalmousemove    Fired on every mouse move, regardless of display object hit.
wheel    Fired when the mouse wheel is scrolled while over the display object.
Touch Events
Event Type    Description
touchstart    Fired when a new touch point is placed on a display object.
touchend    Fired when a touch point is lifted from the display object.
touchendoutside    Fired when a touch point ends outside the object that received touchstart.
touchmove    Fired when a touch point moves across the display object.
touchcancel    Fired when a touch interaction is canceled (e.g. device gesture).
tap    Fired when a touch point taps the display object.
globaltouchmove    Fired on every touch move, regardless of whether a display object is under the touch.
Global Events
In previous versions of PixiJS, events such as pointermove, mousemove, and touchmove were fired when any move event was captured by the canvas, even if the pointer was not over a display object. This behavior changed in v8 and now these events are fired only when the pointer is over a display object.
To maintain the old behavior, you can use the globalpointermove, globalmousemove, and globaltouchmove events. These events are fired on every pointer/touch move, regardless of whether any display object is hit.
const sprite = new Sprite(texture);
sprite.eventMode = 'static';
sprite.on('globalpointermove', (event) => {
    console.log('Pointer moved globally!', event);
});
How Hit Testing Works
When an input event occurs (mouse move, click, etc.), PixiJS walks the display tree to find the top-most interactive element under the pointer:
If interactiveChildren is false on a Container, its children will be skipped.
If a hitArea is set, it overrides bounds-based hit testing.
If eventMode is 'none', the element and its children are skipped.
Once the top-most interactive element is found, the event is dispatched to it. If the event bubbles, it will propagate up the display tree. If the event is not handled, it will continue to bubble up to parent containers until it reaches the root.
Custom Hit Area
Custom hit areas can be defined using the hitArea property. This property can be set on any scene object, including Sprite, Container, and Graphics.
Using a custom hit area allows you to define a specific area for interaction, which can be different from the object's bounding box. It also can improve performance by reducing the number of objects that need to be checked for interaction.
import { Rectangle, Sprite } from 'pixi.js';
const sprite = new Sprite(texture);
sprite.hitArea = new Rectangle(0, 0, 100, 100);
sprite.eventMode = 'static';
Listening to Events
PixiJS supports both on()/off() and addEventListener()/removeEventListener() and event callbacks (onclick: ()=> {}) for adding and removing event listeners. The on() method is recommended for most use cases as it provides a more consistent API across different event types used throughout PixiJS.
Using on() (from EventEmitter)
const eventFn = (e) => console.log('clicked');
sprite.on('pointerdown', eventFn);
sprite.once('pointerdown', eventFn);
sprite.off('pointerdown', eventFn);
Using DOM-style Events
sprite.addEventListener(
    'click',
    (event) => {
        console.log('Clicked!', event.detail);
    },
    { once: true },
);
Using callbacks
sprite.onclick = (event) => {
    console.log('Clicked!', event.detail);
};
Checking for Interactivity
You can check if a Sprite or Container is interactive by using the isInteractive() method. This method returns true if the object is interactive and can receive events.
if (sprite.isInteractive()) {
    // true if eventMode is static or dynamic
}
Custom Cursors
PixiJS allows you to set a custom cursor for interactive objects using the cursor property. This property accepts a string representing the CSS cursor type.
const sprite = new Sprite(texture);
sprite.eventMode = 'static';
sprite.cursor = 'pointer'; // Set the cursor to a pointer when hovering over the sprite
const sprite = new Sprite(texture);
sprite.eventMode = 'static';
sprite.cursor = 'url(my-cursor.png), auto'; // Set a custom cursor image
Default Custom Cursors
You can also set default values to be used for all interactive objects.
// CSS style for icons
const defaultIcon = 'url(\'https://pixijs.com/assets/bunny.png\'),auto';
const hoverIcon = 'url(\'https://pixijs.com/assets/bunny_saturated.png\'),auto';
// Add custom cursor styles
app.renderer.events.cursorStyles.default = defaultIcon;
app.renderer.events.cursorStyles.hover = hoverIcon;
const sprite = new Sprite(texture);
sprite.eventMode = 'static';
sprite.cursor = 'hover';
API Reference
Overview
EventSystem
Cursor
EventMode
Container
FederatedEvent
FederatedMouseEvent
FederatedWheelEvent
FederatedPointerEvent
Math
PixiJS includes a several math utilities for 2D transformations, geometry, and shape manipulation. This guide introduces the most important classes and their use cases, including optional advanced methods enabled via math-extras.
Matrix
The Matrix class represents a 2D affine transformation matrix. It is used extensively for transformations such as scaling, translation, and rotation.
import { Matrix, Point } from 'pixi.js';
const matrix = new Matrix();
matrix.translate(10, 20).scale(2, 2);
const point = new Point(5, 5);
const result = matrix.apply(point); // result is (20, 30)
Point and ObservablePoint
Point
The Point object represents a location in a two-dimensional coordinate system, where x represents the position on the horizontal axis and y represents the position on the vertical axis. Many Pixi functions accept the PointData type as an alternative to Point, which only requires x and y properties.
import { Point } from 'pixi.js';
const point = new Point(5, 10);
point.set(20, 30); // set x and y
ObservablePoint
Extends Point and triggers a callback when its values change. Used internally for reactive systems like position and scale updates.
import { Point, ObservablePoint } from 'pixi.js';
const observer = {
    _onUpdate: (point) => {
        console.log(Point updated to: (${point.x}, ${point.y}));
    },
};
const reactive = new ObservablePoint(observer, 1, 2);
reactive.set(3, 4); // triggers call to _onUpdate
Shapes
PixiJS includes several 2D shapes, used for hit testing, rendering, and geometry computations.
Rectangle
Axis-aligned rectangle defined by x, y, width, and height.
import { Rectangle } from 'pixi.js';
const rect = new Rectangle(10, 10, 100, 50);
rect.contains(20, 20); // true
Circle
Defined by x, y (center) and radius.
import { Circle } from 'pixi.js';
const circle = new Circle(50, 50, 25);
circle.contains(50, 75); // true
Ellipse
Similar to Circle, but supports different width and height (radii).
import { Ellipse } from 'pixi.js';
const ellipse = new Ellipse(0, 0, 20, 10);
ellipse.contains(5, 0); // true
Polygon
Defined by a list of points. Used for complex shapes and hit testing.
import { Polygon } from 'pixi.js';
const polygon = new Polygon([0, 0, 100, 0, 100, 100, 0, 100]);
polygon.contains(50, 50); // true
RoundedRectangle
Rectangle with rounded corners, defined by a radius.
import { RoundedRectangle } from 'pixi.js';
const roundRect = new RoundedRectangle(0, 0, 100, 100, 10);
roundRect.contains(10, 10); // true
Triangle
A convenience wrapper for defining triangles with three points.
import { Triangle } from 'pixi.js';
const triangle = new Triangle(0, 0, 100, 0, 50, 100);
triangle.contains(50, 50); // true
Optional: math-extras
Importing pixi.js/math-extras extends Point and Rectangle with additional vector and geometry utilities.
To enable:
import 'pixi.js/math-extras';
Enhanced Point Methods
Method    Description
add(other[, out])    Adds another point to this one.
subtract(other[, out])    Subtracts another point from this one.
multiply(other[, out])    Multiplies this point with another point component-wise.
multiplyScalar(scalar[, out])    Multiplies the point by a scalar.
dot(other)    Computes the dot product of two vectors.
cross(other)    Computes the scalar z-component of the 3D cross product.
normalize([out])    Returns a normalized (unit-length) vector.
magnitude()    Returns the Euclidean length.
magnitudeSquared()    Returns the squared length (more efficient for comparisons).
project(onto[, out])    Projects this point onto another vector.
reflect(normal[, out])    Reflects the point across a given normal.
Enhanced Rectangle Methods
Method    Description
containsRect(other)    Returns true if this rectangle contains the other.
equals(other)    Checks if all properties are equal.
intersection(other[, out])    Returns a new rectangle representing the overlap.
union(other[, out])    Returns a rectangle that encompasses both rectangles.
PIXI.AnimatedSprite
An AnimatedSprite is a simple way to display an animation depicted by a list of textures.

let alienImages = ["image_sequence_01.png","image_sequence_02.png","image_sequence_03.png","image_sequence_04.png"];
let textureArray = [];

for (let i=0; i < 4; i++)
{
     let texture = PIXI.Texture.from(alienImages[i]);
     textureArray.push(texture);
};

let animatedSprite = new PIXI.AnimatedSprite(textureArray);
The more efficient and simpler way to create an animated sprite is using a PIXI.Spritesheet containing the animation definitions:

PIXI.Loader.shared.add("assets/spritesheet.json").load(setup);

function setup() {
  let sheet = PIXI.Loader.shared.resources["assets/spritesheet.json"].spritesheet;
  animatedSprite = new PIXI.AnimatedSprite(sheet.animations["image_sequence"]);
  ...
}
 new PIXI.AnimatedSprite (textures, autoUpdate)overrides
AnimatedSprite.ts:112
Name    Type    Attributes    Default    Description
textures    PIXI.Texture[] | PIXI.AnimatedSprite.FrameObject[]            
An array of PIXI.Texture or frame objects that make up the animation.

autoUpdate    boolean    <optional>
true    
Whether to use PIXI.Ticker.shared to auto update animation time.

Extends
PIXI.Sprite
Interface Definitions
 FrameObject
Properties:
Name    Type    Description
texture    PIXI.Texture    
The PIXI.Texture of the frame.

time    number    
The duration of the frame, in milliseconds.

Members
 animationSpeed number
The speed that the AnimatedSprite will play at. Higher is faster, lower is slower.

Default Value:
1
 autoUpdate boolean
Whether to use PIXI.Ticker.shared to auto update animation time.

 currentFrame number readonly
The AnimatedSprites current frame index.

 loop boolean
Whether or not the animate sprite repeats after playing.

Default Value:
true
 onComplete () => void
User-assigned function to call when an AnimatedSprite finishes playing.

Example

 animation.onComplete = function () {
   // finished!
 };
 onFrameChange (currentFrame: number) => void
User-assigned function to call when an AnimatedSprite changes which texture is being rendered.

Example

 animation.onFrameChange = function () {
   // updated!
 };
 onLoop () => void
User-assigned function to call when loop is true, and an AnimatedSprite is played and loops around to start again.

Example

 animation.onLoop = function () {
   // looped!
 };
 playing boolean readonly
Indicates if the AnimatedSprite is currently playing.

 textures PIXI.Texture[] | PIXI.AnimatedSprite.FrameObject[]
The array of textures used for this AnimatedSprite.

 totalFrames number readonly
The total number of frames in the AnimatedSprite. This is the same as number of textures assigned to the AnimatedSprite.

Default Value:
0
 updateAnchor boolean
Update anchor to Texture's defaultAnchor when frame changes.

Useful with sprite sheet animations created with tools. Changing anchor for each frame allows to pin sprite origin to certain moving feature of the frame (e.g. left foot).

Note: Enabling this will override any previously set anchor on each frame change.

Default Value:
false
Methods
 PIXI.AnimatedSprite.fromFrames (frames)PIXI.AnimatedSprite static
AnimatedSprite.ts:336
A short hand way of creating an AnimatedSprite from an array of frame ids.

Name    Type    Description
frames    string[]    
The array of frames ids the AnimatedSprite will use as its texture frames.

Returns:
Type    Description
PIXI.AnimatedSprite    
The new animated sprite with the specified frames.
 PIXI.AnimatedSprite.fromImages (images)PIXI.AnimatedSprite static
AnimatedSprite.ts:353
A short hand way of creating an AnimatedSprite from an array of image ids.

Name    Type    Description
images    string[]    
The array of image urls the AnimatedSprite will use as its texture frames.

Returns:
Type    Description
PIXI.AnimatedSprite    The new animate sprite with the specified images as frames.
 destroy (options)void overrides
AnimatedSprite.ts:317
Stops the AnimatedSprite and destroys it.

Name    Type    Attributes    Default    Description
options    object | boolean    <optional>
Options parameter. A boolean will act as if all options have been set to that value.

options.children    boolean    <optional>
false    
If set to true, all the children will have their destroy method called as well. 'options' will be passed on to those calls.

options.texture    boolean    <optional>
false    
Should it destroy the current texture of the sprite as well.

options.baseTexture    boolean    <optional>
false    
Should it destroy the base texture of the sprite as well.

 gotoAndPlay (frameNumber)void
AnimatedSprite.ts:191
Goes to a specific frame and begins playing the AnimatedSprite.

Name    Type    Description
frameNumber    number    
Frame index to start at.

 gotoAndStop (frameNumber)void
AnimatedSprite.ts:173
Stops the AnimatedSprite and goes to a specific frame.

Name    Type    Description
frameNumber    number    
Frame index to stop at.

 play ()void
AnimatedSprite.ts:157
Plays the AnimatedSprite.

 stop ()void
AnimatedSprite.ts:141
Stops the AnimatedSprite.

 update (deltaTime)void
AnimatedSprite.ts:209
Updates the object transform for rendering.

Name    Type    Description
deltaTime    number    
Time since last tick.

Inherited Properties
From class PIXI.Sprite
 anchor PIXI.ObservablePoint inherited
The anchor sets the origin point of the sprite. The default value is taken from the Texture and passed to the constructor.

The default is (0,0), this means the sprite's origin is the top left.

Setting the anchor to (0.5,0.5) means the sprite's origin is centered.

Setting the anchor to (1,1) would mean the sprite's origin point will be the bottom right corner.

If you pass only single parameter, it will set both x and y to the same value as shown in the example below.

Example

 const sprite = new PIXI.Sprite(texture);
 sprite.anchor.set(0.5); // This will set the origin to center. (0.5) is same as (0.5, 0.5).
 blendMode PIXI.BLEND_MODES inherited
The blend mode to be applied to the sprite. Apply a value of PIXI.BLEND_MODES.NORMAL to reset the blend mode.

Default Value:
PIXI.BLEND_MODES.NORMAL
 height number inherited
The height of the sprite, setting this will actually modify the scale to achieve the value set.

 isSprite boolean inherited
Used to fast check if a sprite is.. a sprite!

Default Value:
true
 pluginName string inherited
Plugin that is responsible for rendering this element. Allows to customize the rendering process without overriding '_render' & '_renderCanvas' methods.

Default Value:
'batch'
 roundPixels boolean inherited
If true PixiJS will Math.floor() x/y values when rendering, stopping pixel interpolation.

Advantages can include sharper image quality (like text) and faster rendering on canvas. The main disadvantage is movement of objects may appear less smooth.

To set the global default, change PIXI.settings.ROUND_PIXELS.

Default Value:
false
 texture PIXI.Texture inherited
The texture that the sprite is using.

 tint number inherited
The tint applied to the sprite. This is a hex value.

A value of 0xFFFFFF will remove any tint effect.

Default Value:
0xFFFFFF
 width number inherited
The width of the sprite, setting this will actually modify the scale to achieve the value set.

 _anchor PIXI.ObservablePoint protected inherited
The anchor point defines the normalized coordinates in the texture that map to the position of this sprite.

By default, this is (0,0) (or texture.defaultAnchor if you have modified that), which means the position (x,y) of this Sprite will be the top-left corner.

Note: Updating texture.defaultAnchor after constructing a Sprite does not update its anchor.

https://docs.cocos2d-x.org/cocos2d-x/en/sprites/manipulation.html

Default Value:
this.texture.defaultAnchor
 _cachedTint number protected inherited
Cached tint value so we can tell when the tint is changed. Value is used for 2d CanvasRenderer.

Default Value:
0xFFFFFF
 _height number protected inherited
The height of the sprite (this is initially set by the texture)

 _tintedCanvas HTMLCanvasElement protected inherited
Cached tinted texture.

Default Value:
undefined
 _width number protected inherited
The width of the sprite (this is initially set by the texture).

 uvs Float32Array protected inherited
This is used to store the uvs data of the sprite, assigned at the same time as the vertexData in calculateVertices().

 vertexData Float32Array protected inherited
This is used to store the vertex data of the sprite (basically a quad).

From class PIXI.Container
 children T[] readonly inherited
The array of children of this container.

 interactiveChildren boolean inherited
Determines if the children to the displayObject can be clicked/touched Setting this to false allows PixiJS to bypass a recursive hitTest function

Default Value:
true
 sortableChildren boolean inherited
If set to true, the container will sort its children by zIndex value when updateTransform() is called, or manually if sortChildren() is called.

This actually changes the order of elements in the array, so should be treated as a basic solution that is not performant compared to other solutions, such as @link https://github.com/pixijs/pixi-display

Also be aware of that this may not work nicely with the addChildAt() function, as the zIndex sorting may cause the child to automatically sorted to another position.

See:
PIXI.settings.SORTABLE_CHILDREN
 sortDirty boolean inherited
Should children be sorted by zIndex at the next updateTransform call.

Will get automatically set to true if a new child is added, or if a child's zIndex changes.

From class PIXI.DisplayObject
 _accessibleActive boolean inherited
Default Value:
false
TODO
Needs docs.
 _accessibleDiv boolean inherited
Default Value:
undefined
TODO
Needs docs.
 _bounds PIXI.Bounds inherited
The bounds object, this is used to calculate and store the bounds of the displayObject.

 _localBounds PIXI.Bounds inherited
Local bounds object, swapped with _bounds when using getLocalBounds().

 accessible boolean inherited
Flag for if the object is accessible. If true AccessibilityManager will overlay a shadow div with attributes set

Default Value:
false
 accessibleChildren boolean inherited
Setting to false will prevent any children inside this container to be accessible. Defaults to true.

Default Value:
true
 accessibleHint string inherited
Sets the aria-label attribute of the shadow div

Default Value:
undefined
 accessiblePointerEvents string inherited
Specify the pointer-events the accessible div will use Defaults to auto.

Default Value:
'auto'
 accessibleTitle ?string inherited
Sets the title attribute of the shadow div If accessibleTitle AND accessibleHint has not been this will default to 'displayObject [tabIndex]'

Default Value:
undefined
 accessibleType string inherited
Specify the type of div the accessible layer is. Screen readers treat the element differently depending on this type. Defaults to button.

Default Value:
'button'
 alpha number inherited
The opacity of the object.

 angle number inherited
The angle of the object in degrees. 'rotation' and 'angle' have the same effect on a display object; rotation is in radians, angle is in degrees.

 buttonMode boolean inherited
If enabled, the mouse cursor use the pointer behavior when hovered over the displayObject if it is interactive Setting this changes the 'cursor' property to 'pointer'.

Example

 const sprite = new PIXI.Sprite(texture);
 sprite.interactive = true;
 sprite.buttonMode = true;
 cacheAsBitmap boolean inherited
Set this to true if you want this display object to be cached as a bitmap. This basically takes a snap shot of the display object as it is at that moment. It can provide a performance benefit for complex static displayObjects. To remove simply set this property to false

IMPORTANT GOTCHA - Make sure that all your textures are preloaded BEFORE setting this property to true as it will take a snapshot of what is currently there. If the textures have not loaded then they will not appear.

 cacheAsBitmapMultisample number inherited
The number of samples to use for cacheAsBitmap. If set to null, the renderer's sample count is used. If cacheAsBitmap is set to true, this will re-render with the new number of samples.

Default Value:
PIXI.MSAA_QUALITY.NONE
 cacheAsBitmapResolution number inherited
The resolution to use for cacheAsBitmap. By default this will use the renderer's resolution but can be overriden for performance. Lower values will reduce memory usage at the expense of render quality. A falsey value of null or 0 will default to the renderer's resolution. If cacheAsBitmap is set to true, this will re-render with the new resolution.

Default Value:
null
 cullable boolean inherited
Should this object be rendered if the bounds of this object are out of frame?

Culling has no effect on whether updateTransform is called.

 cullArea PIXI.Rectangle inherited
If set, this shape is used for culling instead of the bounds of this object. It can improve the culling performance of objects with many children. The culling area is defined in local space.

 cursor string inherited
This defines what cursor mode is used when the mouse cursor is hovered over the displayObject.

Default Value:
undefined
See:
https://developer.mozilla.org/en/docs/Web/CSS/cursor
Example

 const sprite = new PIXI.Sprite(texture);
 sprite.interactive = true;
 sprite.cursor = 'wait';
 filterArea PIXI.Rectangle inherited
The area the filter is applied to. This is used as more of an optimization rather than figuring out the dimensions of the displayObject each frame you can set this rectangle.

Also works as an interaction mask.

 filters PIXI.Filter[] | null inherited
Sets the filters for the displayObject. IMPORTANT: This is a WebGL only feature and will be ignored by the canvas renderer. To remove filters simply set this property to 'null'.

 hitArea PIXI.IHitArea inherited
Interaction shape. Children will be hit first, then this shape will be checked. Setting this will cause this shape to be checked in hit tests rather than the displayObject's bounds.

Default Value:
undefined
Example

 const sprite = new PIXI.Sprite(texture);
 sprite.interactive = true;
 sprite.hitArea = new PIXI.Rectangle(0, 0, 100, 100);
 interactive boolean inherited
Enable interaction events for the DisplayObject. Touch, pointer and mouse events will not be emitted unless interactive is set to true.

Default Value:
false
Example

 const sprite = new PIXI.Sprite(texture);
 sprite.interactive = true;
 sprite.on('tap', (event) => {
    //handle event
 });
 isMask boolean inherited
Does any other displayObject use this object as a mask?

 localTransform PIXI.Matrix readonly inherited
Current transform of the object based on local factors: position, scale, other stuff.

 mask PIXI.Container | PIXI.MaskData | null inherited
Sets a mask for the displayObject. A mask is an object that limits the visibility of an object to the shape of the mask applied to it. In PixiJS a regular mask must be a PIXI.Graphics or a PIXI.Sprite object. This allows for much faster masking in canvas as it utilities shape clipping. Furthermore, a mask of an object must be in the subtree of its parent. Otherwise, getLocalBounds may calculate incorrect bounds, which makes the container's width and height wrong. To remove a mask, set this property to null.

For sprite mask both alpha and red channel are used. Black mask is the same as transparent mask.

TODO
At the moment, PIXI.CanvasRenderer doesn't support PIXI.Sprite as mask.
Example

 const graphics = new PIXI.Graphics();
 graphics.beginFill(0xFF3300);
 graphics.drawRect(50, 250, 100, 100);
 graphics.endFill();

 const sprite = new PIXI.Sprite(texture);
 sprite.mask = graphics;
 name string inherited
The instance name of the object.

Default Value:
undefined
 parent PIXI.Container inherited
The display object container that contains this display object.

 pivot PIXI.ObservablePoint inherited
The center of rotation, scaling, and skewing for this display object in its local space. The position is the projection of pivot in the parent's local space.

By default, the pivot is the origin (0, 0).

Since:
4.0.0
 position PIXI.ObservablePoint inherited
The coordinate of the object relative to the local coordinates of the parent.

Since:
4.0.0
 renderable boolean inherited
Can this object be rendered, if false the object will not be drawn but the updateTransform methods will still be called.

Only affects recursive calls from parent. You can ask for bounds manually.

 rotation number inherited
The rotation of the object in radians. 'rotation' and 'angle' have the same effect on a display object; rotation is in radians, angle is in degrees.

 scale PIXI.ObservablePoint inherited
The scale factors of this object along the local coordinate axes.

The default scale is (1, 1).

Since:
4.0.0
 skew PIXI.ObservablePoint inherited
The skew factor for the object in radians.

Since:
4.0.0
 transform PIXI.Transform inherited
World transform and local transform of this object. This will become read-only later, please do not assign anything there unless you know what are you doing.

 visible boolean inherited
The visibility of the object. If false the object will not be drawn, and the updateTransform function will not be called.

Only affects recursive calls from parent. You can ask for bounds or call updateTransform manually.

 worldAlpha number readonly inherited
The multiplied alpha of the displayObject.

 worldTransform PIXI.Matrix readonly inherited
Current transform of the object based on world (parent) factors.

 worldVisible boolean readonly inherited
Indicates if the object is globally visible.

 x number inherited
The position of the displayObject on the x axis relative to the local coordinates of the parent. An alias to position.x

 y number inherited
The position of the displayObject on the y axis relative to the local coordinates of the parent. An alias to position.y

 zIndex number inherited
The zIndex of the displayObject.

If a container has the sortableChildren property set to true, children will be automatically sorted by zIndex value; a higher value will mean it will be moved towards the end of the array, and thus rendered on top of other display objects within the same container.

See:
PIXI.Container#sortableChildren
 _boundsID number protected inherited
Flags the cached bounds as dirty.

 _boundsRect PIXI.Rectangle protected inherited
Cache of this display-object's bounds-rectangle.

 _destroyed boolean protected inherited
If the object has been destroyed via destroy(). If true, it should not be used.

 _enabledFilters PIXI.Filter[] protected inherited
Currently enabled filters.

 _lastSortedIndex number protected inherited
Which index in the children array the display component was before the previous zIndex sort. Used by containers to help sort objects with the same zIndex, by using previous array index as the decider.

 _localBoundsRect PIXI.Rectangle protected inherited
Cache of this display-object's local-bounds rectangle.

 _mask PIXI.Container | PIXI.MaskData protected inherited
The original, cached mask of the object.

 _tempDisplayObjectParent PIXI.Container protected inherited
 _zIndex number protected inherited
The zIndex of the displayObject. A higher value will mean it will be rendered on top of other displayObjects within the same container.

Inherited Methods
From class PIXI.Sprite
 calculateTrimmedVertices ()void inherited
Sprite.ts:303
Calculates worldTransform * vertices for a non texture with a trim. store it in vertexTrimmedData.

This is used to ensure that the true width and height of a trimmed texture is respected.

 calculateVertices ()void inherited
Sprite.ts:219
Calculates worldTransform * vertices, store it in vertexData.

 containsPoint (point)boolean inherited
Sprite.ts:430
Tests if a point is inside this sprite

Name    Type    Description
point    IPointData    
the point to test

Returns:
Type    Description
boolean    The result of the test
 getLocalBounds (rect)PIXI.Rectangle inherited
Sprite.ts:394
Gets the local bounds of the sprite object.

Name    Type    Attributes    Description
rect    PIXI.Rectangle    <optional>
Optional output rectangle.

Returns:
Type    Description
PIXI.Rectangle    The bounds.
 _calculateBounds ()void protected inherited
Sprite.ts:373
Updates the bounds of the sprite.

 _onTextureUpdate ()void protected inherited
Sprite.ts:193
When the texture is updated, this event will fire to update the scale and frame.

 _render (renderer)void protected inherited
Sprite.ts:360
Renders the object using the WebGL renderer

Name    Type    Description
renderer    PIXI.Renderer    
The webgl renderer to use.

From class PIXI.Container
 addChild (…children)PIXI.DisplayObject inherited
Container.ts:124
Adds one or more children to the container.

Multiple items can be added like so: myContainer.addChild(thingOne, thingTwo, thingThree)

Name    Type    Description
children    PIXI.DisplayObject    
The DisplayObject(s) to add to the container

Returns:
Type    Description
PIXI.DisplayObject    
The first child that was added.
 addChildAt (child, index)PIXI.DisplayObject inherited
Container.ts:173
Adds a child to the container at a specified index. If the index is out of bounds an error will be thrown

Name    Type    Description
child    PIXI.DisplayObject    
The child to add

index    number    
The index to place the child in

Returns:
Type    Description
PIXI.DisplayObject    The child that was added.
 calculateBounds ()void inherited
Container.ts:444
Recalculates the bounds of the container.

This implementation will automatically fit the children's bounds into the calculation. Each child's bounds is limited to its mask's bounds or filterArea, if any is applied.

 containerUpdateTransform inherited
Container.ts:814
Container default updateTransform, does update children of container. Will crash if there's no parent element.

 getChildAt (index)T inherited
Container.ts:267
Returns the child at the specified index

Name    Type    Description
index    number    
The index to get the child at

Returns:
Type    Description
T    
The child at the given index, if any.
 getChildByName (name, deep)PIXI.DisplayObject inherited
index.ts:10
Returns the display object in the container.

Recursive searches are done in a preorder traversal.

Name    Type    Attributes    Default    Description
name    string            
Instance name.

deep    boolean    <optional>
false    
Whether to search recursively

Returns:
Type    Description
PIXI.DisplayObject    The child with the specified name.
 getChildIndex (child)number inherited
Container.ts:230
Returns the index position of a child DisplayObject instance

Name    Type    Description
child    T    
The DisplayObject instance to identify

Returns:
Type    Description
number    
The index position of the child display object to identify
 removeChild (…children)PIXI.DisplayObject inherited
Container.ts:282
Removes one or more children from the container.

Name    Type    Description
children    PIXI.DisplayObject    
The DisplayObject(s) to remove

Returns:
Type    Description
PIXI.DisplayObject    The first child that was removed.
 removeChildAt (index)T inherited
Container.ts:322
Removes a child from the specified index position.

Name    Type    Description
index    number    
The index to get the child from

Returns:
Type    Description
T    The child that was removed.
 removeChildren (beginIndex, endIndex)T[] inherited
Container.ts:347
Removes all children from this container that are within the begin and end indexes.

Name    Type    Default    Description
beginIndex        0    
The beginning position.

endIndex            
The ending position. Default value is size of the container.

Returns:
Type    Description
T[]    
List of removed children
 render (renderer)void inherited
Container.ts:600
Renders the object using the WebGL renderer.

The _render method is be overriden for rendering the contents of the container itself. This render method will invoke it, and also invoke the render methods of all children afterward.

If renderable or visible is false or if worldAlpha is not positive or if cullable is true and the bounds of this object are out of frame, this implementation will entirely skip rendering. See PIXI.DisplayObject for choosing between renderable or visible. Generally, setting alpha to zero is not recommended for purely skipping rendering.

When your scene becomes large (especially when it is larger than can be viewed in a single screen), it is advised to employ culling to automatically skip rendering objects outside of the current screen. See cullable and cullArea. Other culling methods might be better suited for a large number static objects; see @pixi-essentials/cull and pixi-cull.

The renderAdvanced method is internally used when when masking or filtering is applied on a container. This does, however, break batching and can affect performance when masking and filtering is applied extensively throughout the scene graph.

Name    Type    Description
renderer    PIXI.Renderer    
The renderer

 renderCanvas (renderer)void inherited
Container.ts:17
Renders the object using the Canvas renderer

Name    Type    Description
renderer    PIXI.CanvasRenderer    
The renderer

 setChildIndex (child, index)void inherited
Container.ts:247
Changes the position of an existing child in the display object container

Name    Type    Description
child    T    
The child DisplayObject instance for which you want to change the index number

index    number    
The resulting index number for the child display object

 sortChildren ()void inherited
Container.ts:393
Sorts children by zIndex. Previous order is maintained for 2 children with the same zIndex.

 swapChildren (child, child2)void inherited
Container.ts:210
Swaps the position of 2 Display Objects within this container.

Name    Type    Description
child    T    
First display object to swap

child2    T    
Second display object to swap

 updateTransform ()void inherited
Container.ts:418
Updates the transform on all children of this container for rendering.

 _renderWithCulling (renderer)void protected inherited
Container.ts:536
Renders this object and its children with culling.

Name    Type    Description
renderer    PIXI.Renderer    
The renderer

 onChildrenChange (_length)void protected inherited
Container.ts:115
Overridable method that can be used by Container subclasses whenever the children array is modified.

Name    Type    Attributes    Description
_length    number    <optional>
 renderAdvanced (renderer)void protected inherited
Container.ts:652
Render the object using the WebGL renderer and advanced features.

Name    Type    Description
renderer    PIXI.Renderer    
The renderer

From class PIXI.DisplayObject
 addEventListener (type, listener, options)inherited
FederatedEventTarget.ts:110
Unlike on or addListener which are methods from EventEmitter, addEventListener seeks to be compatible with the DOM's addEventListener with support for options. IMPORTANT: Only available if using the @pixi/events package.

Name    Type    Attributes    Description
type    string        
The type of event to listen to.

listener    EventListenerOrEventListenerObject        
The listener callback or object.

options    boolean | AddEventListenerOptions    <optional>
Listener options, used for capture phase.

Example

 // Tell the user whether they did a single, double, triple, or nth click.
 button.addEventListener('click', {
   handleEvent(e): {
     let prefix;

     switch (e.detail) {
       case 1: prefix = 'single'; break;
       case 2: prefix = 'double'; break;
       case 3: prefix = 'triple'; break;
       default: prefix = e.detail + 'th'; break;
     }

     console.log('That was a ' + prefix + 'click');
   }
 });

 // But skip the first click!
 button.parent.addEventListener('click', function blockClickOnce(e) {
   e.stopImmediatePropagation();
   button.parent.removeEventListener('click', blockClickOnce, true);
 }, {
   capture: true,
 })
 disableTempParent (cacheParent)void inherited
DisplayObject.ts:748
Pair method for enableTempParent

Name    Type    Description
cacheParent    PIXI.Container    
Actual parent of element

 dispatchEvent (e)boolean inherited
FederatedEventTarget.ts:184
Dispatch the event on this PIXI.DisplayObject using the event's PIXI.EventBoundary.

The target of the event is set to this and the defaultPrevented flag is cleared before dispatch.

IMPORTANT: Only available if using the @pixi/events package.

Name    Type    Description
e    Event    
The event to dispatch.

Returns:
Type    Description
boolean    Whether the preventDefault() method was not invoked.
Example

 // Reuse a click event!
 button.dispatchEvent(clickEvent);
 displayObjectUpdateTransform inherited
DisplayObject.ts:1015
DisplayObject default updateTransform, does not update children of container. Will crash if there's no parent element.

 enableTempParent ()PIXI.Container inherited
DisplayObject.ts:729
Used in Renderer, cacheAsBitmap and other places where you call an updateTransform on root

const cacheParent = elem.enableTempParent();
elem.updateTransform();
elem.disableTempParent(cacheParent);
Returns:
Type    Description
PIXI.Container    
current parent
 getBounds (skipUpdate, rect)PIXI.Rectangle inherited
DisplayObject.ts:451
Calculates and returns the (world) bounds of the display object as a Rectangle.

This method is expensive on containers with a large subtree (like the stage). This is because the bounds of a container depend on its children's bounds, which recursively causes all bounds in the subtree to be recalculated. The upside, however, is that calling getBounds once on a container will indeed update the bounds of all children (the whole subtree, in fact). This side effect should be exploited by using displayObject._bounds.getRectangle() when traversing through all the bounds in a scene graph. Otherwise, calling getBounds on each object in a subtree will cause the total cost to increase quadratically as its height increases.

The transforms of all objects in a container's subtree and of all ancestors are updated. The world bounds of all display objects in a container's subtree will also be recalculated.

The _bounds object stores the last calculation of the bounds. You can use to entirely skip bounds calculation if needed.

const lastCalculatedBounds = displayObject._bounds.getRectangle(optionalRect);
Do know that usage of getLocalBounds can corrupt the _bounds of children (the whole subtree, actually). This is a known issue that has not been solved. See getLocalBounds for more details.

getBounds should be called with skipUpdate equal to true in a render() call. This is because the transforms are guaranteed to be update-to-date. In fact, recalculating inside a render() call may cause corruption in certain cases.

Name    Type    Attributes    Description
skipUpdate    boolean    <optional>
Setting to true will stop the transforms of the scene graph from being updated. This means the calculation returned MAY be out of date BUT will give you a nice performance boost.

rect    PIXI.Rectangle    <optional>
Optional rectangle to store the result of the bounds calculation.

Returns:
Type    Description
PIXI.Rectangle    
The minimum axis-aligned rectangle in world space that fits around this object.
 getGlobalPosition (point, skipUpdate)PIXI.Point inherited
index.ts:4
Returns the global position of the displayObject. Does not depend on object scale, rotation and pivot.

Name    Type    Attributes    Default    Description
point    PIXI.Point    <optional>
new PIXI.Point()    
The point to write the global value to.

skipUpdate    boolean    <optional>
false    
Setting to true will stop the transforms of the scene graph from being updated. This means the calculation returned MAY be out of date BUT will give you a nice performance boost.

Returns:
Type    Description
PIXI.Point    The updated point.
 removeEventListener (type, listener, options)inherited
FederatedEventTarget.ts:159
Unlike off or removeListener which are methods from EventEmitter, removeEventListener seeks to be compatible with the DOM's removeEventListener with support for options. IMPORTANT: Only available if using the @pixi/events package.

Name    Type    Attributes    Description
type    string        
The type of event the listener is bound to.

listener    EventListenerOrEventListenerObject        
The listener callback or object.

options    boolean | AddEventListenerOptions    <optional>
The original listener options. This is required to deregister a capture phase listener.

 setParent (container)PIXI.Container inherited
DisplayObject.ts:637
Set the parent Container of this DisplayObject.

Name    Type    Description
container    PIXI.Container    
The Container to add this DisplayObject to.

Returns:
Type    Description
PIXI.Container    
The Container that this DisplayObject was added to.
 setTransform (x, y, scaleX, scaleY, rotation, skewX, skewY, pivotX, pivotY)this inherited
DisplayObject.ts:654
Convenience function to set the position, scale, skew and pivot at once.

Name    Type    Default    Description
x        0    
The X position

y        0    
The Y position

scaleX        1    
The X scale value

scaleY        1    
The Y scale value

rotation        0    
The rotation

skewX        0    
The X skew value

skewY        0    
The Y skew value

pivotX        0    
The X pivot value

pivotY        0    
The Y pivot value

Returns:
Type    Description
this    
The DisplayObject instance
 toGlobal (position, point, skipUpdate)P inherited
DisplayObject.ts:565
Calculates the global position of the display object.

Name    Type    Attributes    Description
position    IPointData        
The world origin to calculate from.

point    P    <optional>
A Point object in which to store the value, optional (otherwise will create a new Point).

skipUpdate            
Should we skip the update transform.

Returns:
Type    Description
P    
A point object representing the position of this object.
 toLocal (position, from, point, skipUpdate)P inherited
DisplayObject.ts:598
Calculates the local position of the display object relative to another point.

Name    Type    Attributes    Description
position    IPointData        
The world origin to calculate from.

from    PIXI.DisplayObject    <optional>
The DisplayObject to calculate the global position from.

point    P    <optional>
A Point object in which to store the value, optional (otherwise will create a new Point).

skipUpdate    boolean    <optional>
Should we skip the update transform

Returns:
Type    Description
P    
A point object representing the position of this object
 _recursivePostUpdateTransform ()void protected inherited
DisplayObject.ts:427
Recursively updates transform of all objects from the root to this one internal function for toLocal()

Inherited Events
From class PIXI.Container
 childAdded inherited
Container.ts:98
Fired when a DisplayObject is added to this Container.

Name    Type    Description
child    PIXI.DisplayObject    
The child added to the Container.

container    PIXI.Container    
The container that added the child.

index    number    
The children's index of the added child.

From class PIXI.DisplayObject
 added inherited
DisplayObject.ts:389
Fired when this DisplayObject is added to a Container.

Name    Type    Description
container    PIXI.Container    
The container added to.

 childRemoved inherited
Container.ts:106
Fired when a DisplayObject is removed from this Container.

Name    Type    Description
child    PIXI.DisplayObject    
The child removed from the Container.

container    PIXI.Container    
The container that removed the child.

index    number    
The former children's index of the removed child

 click inherited
EventBoundary.ts:1397
Fired when a pointer device button (usually a mouse left-button) is pressed and released on the display object. DisplayObject's interactive property must be set to true to fire event.

A click event fires after the pointerdown and pointerup events, in that order. If the mouse is moved over another DisplayObject after the pointerdown event, the click event is fired on the most specific common ancestor of the two target DisplayObjects.

The detail property of the event is the number of clicks that occurred within a 200ms window of each other upto the current click. For example, it will be 2 for a double click.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 clickcapture inherited
EventBoundary.ts:1413
Capture phase equivalent of click.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 destroyed inherited
DisplayObject.ts:403
Fired when this DisplayObject is destroyed. This event is emitted once destroy is finished.

 mousedown inherited
EventBoundary.ts:1329
Fired when a mouse button (usually a mouse left-button) is pressed on the display. object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
The mousedown event.

 mousedowncapture inherited
EventBoundary.ts:1338
Capture phase equivalent of mousedown.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
The capture phase mousedown.

 mouseenter inherited
EventBoundary.ts:1516
Fired when the mouse pointer is moved over a DisplayObject and its descendant's hit testing boundaries.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mouseentercapture inherited
EventBoundary.ts:1524
Capture phase equivalent of mouseenter

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mouseleave inherited
EventBoundary.ts:1552
Fired when the mouse pointer exits a DisplayObject and its descendants.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
 mouseleavecapture inherited
EventBoundary.ts:1560
Capture phase equivalent of mouseleave.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mousemove inherited
EventBoundary.ts:1482
Fired when a pointer device (usually a mouse) is moved while over the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mousemovecature inherited
EventBoundary.ts:1491
Capture phase equivalent of mousemove.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mouseout inherited
EventBoundary.ts:1532
Fired when a pointer device (usually a mouse) is moved off the display object. DisplayObject's interactive property must be set to true to fire event.

This may be fired on a DisplayObject that was removed from the scene graph immediately after a mouseover event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mouseoutcapture inherited
EventBoundary.ts:1544
Capture phase equivalent of mouseout.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mouseover inherited
EventBoundary.ts:1499
Fired when a pointer device (usually a mouse) is moved onto the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mouseovercapture inherited
EventBoundary.ts:1508
Capture phase equivalent of mouseover.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mouseup inherited
EventBoundary.ts:1363
Fired when a pointer device button (usually a mouse left-button) is released over the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mouseupcature inherited
EventBoundary.ts:1372
Capture phase equivalent of mouseup.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mouseupoutside inherited
EventBoundary.ts:1440
Fired when a pointer device button (usually a mouse left-button) is released outside the display object that initially registered a mousedown. DisplayObject's interactive property must be set to true to fire event.

This event is specific to the Federated Events API. It does not have a capture phase, unlike most of the other events. It only bubbles to the most specific ancestor of the targets of the corresponding pointerdown and pointerup events, i.e. the target of the click event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 mouseupoutsidecapture inherited
EventBoundary.ts:1455
Capture phase equivalent of mouseupoutside.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointercancel inherited
EventBoundary.ts:1602
Fired when the operating system cancels a pointer event. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointercancelcapture inherited
EventBoundary.ts:1611
Capture phase equivalent of pointercancel.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerdown inherited
EventBoundary.ts:1568
Fired when a pointer device button is pressed on the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerdowncapture inherited
EventBoundary.ts:1577
Capture phase equivalent of pointerdown.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerenter inherited
EventBoundary.ts:1692
Fired when the pointer is moved over a DisplayObject and its descendant's hit testing boundaries.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerentercapture inherited
EventBoundary.ts:1700
Capture phase equivalent of pointerenter

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerleave inherited
EventBoundary.ts:1725
Fired when the pointer leaves the hit testing boundaries of a DisplayObject and its descendants.

This event notifies only the target and does not bubble.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
The pointerleave event.

 pointerleavecapture inherited
EventBoundary.ts:1735
Capture phase equivalent of pointerleave.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointermove inherited
EventBoundary.ts:1658
Fired when a pointer device is moved while over the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointermovecapture inherited
EventBoundary.ts:1667
Capture phase equivalent of pointermove.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerout inherited
EventBoundary.ts:1708
Fired when a pointer device is moved off the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointeroutcapture inherited
EventBoundary.ts:1717
Capture phase equivalent of pointerout.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerover inherited
EventBoundary.ts:1675
Fired when a pointer device is moved onto the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerovercapture inherited
EventBoundary.ts:1684
Capture phase equivalent of pointerover.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointertap inherited
EventBoundary.ts:1619
Fired when a pointer device button is pressed and released on the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointertapcapture inherited
EventBoundary.ts:1628
Capture phase equivalent of pointertap.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerup inherited
EventBoundary.ts:1585
Fired when a pointer device button is released over the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerupcapture inherited
EventBoundary.ts:1594
Capture phase equivalent of pointerup.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerupoutside inherited
EventBoundary.ts:1636
Fired when a pointer device button is released outside the display object that initially registered a pointerdown. DisplayObject's interactive property must be set to true to fire event.

This event is specific to the Federated Events API. It does not have a capture phase, unlike most of the other events. It only bubbles to the most specific ancestor of the targets of the corresponding pointerdown and pointerup events, i.e. the target of the click event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 pointerupoutsidecapture inherited
EventBoundary.ts:1650
Capture phase equivalent of pointerupoutside.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 removed inherited
DisplayObject.ts:396
Fired when this DisplayObject is removed from a Container.

Name    Type    Description
container    PIXI.Container    
The container removed from.

 rightclick inherited
EventBoundary.ts:1421
Fired when a pointer device secondary button (usually a mouse right-button) is pressed and released on the display object. DisplayObject's interactive property must be set to true to fire event.

This event follows the semantics of click.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 rightclickcapture inherited
EventBoundary.ts:1432
Capture phase equivalent of rightclick.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 rightdown inherited
EventBoundary.ts:1346
Fired when a pointer device secondary button (usually a mouse right-button) is pressed on the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 rightdowncapture inherited
EventBoundary.ts:1355
Capture phase equivalent of rightdown.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
The rightdowncapture event.

 rightup inherited
EventBoundary.ts:1380
Fired when a pointer device secondary button (usually a mouse right-button) is released over the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 rightupcapture inherited
EventBoundary.ts:1389
Capture phase equivalent of rightup.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 rightupoutside inherited
EventBoundary.ts:1463
Fired when a pointer device secondary button (usually a mouse right-button) is released outside the display object that initially registered a rightdown. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 rightupoutsidecapture inherited
EventBoundary.ts:1474
Capture phase equivalent of rightupoutside.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 tap inherited
EventBoundary.ts:1794
Fired when a touch point is placed and removed from the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 tapcapture inherited
EventBoundary.ts:1803
Capture phase equivalent of tap.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 touchcancel inherited
EventBoundary.ts:1777
Fired when the operating system cancels a touch. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 touchcancelcapture inherited
EventBoundary.ts:1786
Capture phase equivalent of touchcancel.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 touchend inherited
EventBoundary.ts:1760
Fired when a touch point is removed from the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 touchendcapture inherited
EventBoundary.ts:1769
Capture phase equivalent of touchend.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 touchendoutside inherited
EventBoundary.ts:1811
Fired when a touch point is removed outside of the display object that initially registered a touchstart. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 touchendoutsidecapture inherited
EventBoundary.ts:1821
Capture phase equivalent of touchendoutside.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 touchmove inherited
EventBoundary.ts:1829
Fired when a touch point is moved along the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 touchmovecapture inherited
EventBoundary.ts:1838
Capture phase equivalent of touchmove.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 touchstart inherited
EventBoundary.ts:1743
Fired when a touch point is placed on the display object. DisplayObject's interactive property must be set to true to fire event.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 touchstartcapture inherited
EventBoundary.ts:1752
Capture phase equivalent of touchstart.

These events are propagating from the EventSystem in @pixi/events.

Name    Type    Description
event    PIXI.FederatedPointerEvent    
Event

 wheel inherited
EventBoundary.ts:1846
Fired when a the user scrolls with the mouse cursor over a DisplayObject.

These events are propagating from the EventSystem in @pixi/events.

Type:
PIXI.FederatedWheelEvent
 wheelcapture inherited
EventBoundary.ts:1854
Capture phase equivalent of wheel.

These events are propagating from the EventSystem in @pixi/events.

Type:
PIXI.FederatedWheelEvent
PIXI.Spritesheet
Utility class for maintaining reference to a collection of Textures on a single Spritesheet.

To access a sprite sheet from your code you may pass its JSON data file to Pixi's loader:

PIXI.Loader.shared.add("images/spritesheet.json").load(setup);

function setup() {
  let sheet = PIXI.Loader.shared.resources["images/spritesheet.json"].spritesheet;
  ...
}
Alternately, you may circumvent the loader by instantiating the Spritesheet directly:

const sheet = new PIXI.Spritesheet(texture, spritesheetData);
await sheet.parse();
console.log('Spritesheet ready to use!');
With the sheet.textures you can create Sprite objects,sheet.animations can be used to create an AnimatedSprite.

Sprite sheets can be packed using tools like TexturePacker, Shoebox or Spritesheet.js. Default anchor points (see PIXI.Texture#defaultAnchor) and grouping of animation sprites are currently only supported by TexturePacker.

 new PIXI.Spritesheet (texture, data, resolutionFilename)
Spritesheet.ts:134
Name    Type    Description
texture    PIXI.BaseTexture | PIXI.Texture    
Reference to the source BaseTexture object.

data    object    
Spritesheet image data.

resolutionFilename        
The filename to consider when determining the resolution of the spritesheet. If not provided, the imageUrl will be used on the BaseTexture.

Members
 PIXI.Spritesheet.BATCH_SIZE number staticreadonly
The maximum number of Textures to build per process.

Default Value:
1000
 animations Dict<PIXI.Texture[]>
A map containing the textures for each animation. Can be used to create an AnimatedSprite:

new PIXI.AnimatedSprite(sheet.animations["anim_name"])
 baseTexture PIXI.BaseTexture
Reference to ths source texture.

 data object
Reference to the original JSON data.

 linkedSheets PIXI.Spritesheet[]
For multi-packed spritesheets, this contains a reference to all the other spritesheets it depends on.

 resolution number
The resolution of the spritesheet.

 textures Dict<PIXI.Texture>
A map containing all textures of the sprite sheet. Can be used to create a Sprite:

new PIXI.Sprite(sheet.textures["image.png"]);
Methods
 destroy (destroyBase)void
Spritesheet.ts:358
Destroy Spritesheet and don't use after this.

Name    Type    Attributes    Default    Description
destroyBase    boolean    <optional>
false    
Whether to destroy the base texture as well

 parse ()Promise<PIXI.Texture<Dict>>
Spritesheet.ts:188
Parser spritesheet from loaded data. This is done asynchronously to prevent creating too many Texture within a single process.

Returns:
Type    Description
Promise<PIXI.Texture<Dict>>    

study all methods in detail - take notice of everything that surprises you and you did not take in consideration - and especially notcie things that are any patterns in my app current design (and in teh design we were planning)

Focus on the new plan where react is fully abandoned from the game part and only coverse the ui 
like the current tiles drawing 
let's think about entities drawing and using the animated sprites callback
and let's think about seamless integrating animation transitiion / their callbacks / the event streams (also handling a qeueu of events to render if we are behind etc)